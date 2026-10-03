"""Separate training worker: python worker.py. Each fit runs in a bounded child."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import socket


def worker_identity():
    return os.getenv("DAISY_WORKER_ID") or socket.gethostname()


def execute_file(job_path, result_path):
    from fastapi import Request
    import main
    job = json.loads(Path(job_path).read_text(encoding="utf-8"))
    request = Request({"type": "http", "state": {"user": {"id": job["owner_id"]}}})
    try:
        with main.DATASETS.lease():
            result = main.execute_model_training(main.ModelTrainingRequest(**job["payload"]), request)
        out = {"result": result}
    except Exception:
        import logging
        logging.getLogger("daisy.worker").exception("Training job failed")
        out = {"error": "Training failed. Check the worker log and dataset configuration."}
    Path(result_path).write_text(json.dumps(out, allow_nan=False), encoding="utf-8")


def process_job(queue, job, timeout=600, runner=subprocess.Popen, worker_id=None):
    """Cancellation and timeout terminate the fit instead of abandoning a thread."""
    identifier, owner = job["id"], job["owner_id"]
    if queue.get(identifier, owner)["status"] != "running":
        return
    with tempfile.TemporaryDirectory() as directory:
        input_path, output_path = Path(directory) / "job.json", Path(directory) / "result.json"
        input_path.write_text(json.dumps(job), encoding="utf-8")
        env = dict(os.environ, OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
        process = runner([sys.executable, str(Path(__file__).resolve()), "--execute", str(input_path), str(output_path)], env=env)
        started = time.monotonic()
        heartbeat_at = started - 15
        try:
            while process.poll() is None:
                if worker_id and time.monotonic() - heartbeat_at >= 15:
                    queue.heartbeat(worker_id, "running")
                    heartbeat_at = time.monotonic()
                state = queue.get(identifier, owner)
                if state["status"] == "cancelled" or time.monotonic() - started > timeout:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                    if state["status"] != "cancelled":
                        queue.finish(identifier, owner, "failed", error="Training exceeded the 10 minute limit.")
                    return
                time.sleep(1)
            if process.returncode != 0 or not output_path.is_file():
                queue.finish(identifier, owner, "failed", error="Training worker exited unexpectedly.")
                return
            output = json.loads(output_path.read_text(encoding="utf-8"))
            queue.finish(identifier, owner, "failed" if "error" in output else "completed", result=output.get("result"), error=output.get("error"))
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


def main_loop():
    import main
    if main.job_queue is None:
        raise SystemExit("Enable sqlite or supabase persistence before starting the worker.")
    print("DAISY training worker ready; one fit at a time, 10 minute job limit.", flush=True)
    worker_id = worker_identity()
    heartbeat_at = 0
    while True:
        try:
            if time.monotonic() - heartbeat_at >= 15:
                main.job_queue.heartbeat(worker_id, "idle")
                heartbeat_at = time.monotonic()
            job = main.job_queue.claim()
            if job:
                process_job(main.job_queue, job, worker_id=worker_id)
                main.job_queue.heartbeat(worker_id, "idle")
                heartbeat_at = time.monotonic()
            else:
                time.sleep(2)
        except KeyboardInterrupt:
            main.job_queue.heartbeat(worker_id, "stopped")
            break
        except Exception:
            import logging
            logging.getLogger("daisy.worker").exception("Worker queue unavailable")
            time.sleep(5)


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--healthcheck":
        import main
        raise SystemExit(0 if main.job_queue and main.job_queue.worker_ready(worker_identity()) else 1)
    elif len(sys.argv) == 4 and sys.argv[1] == "--execute":
        execute_file(sys.argv[2], sys.argv[3])
    else:
        main_loop()
