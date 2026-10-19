import { useEffect, useState, type ReactNode, type FormEvent } from "react";
import { useConvexAuth, useMutation, usePaginatedQuery, useQuery } from "convex/react";
import { api } from "../../convex/_generated/api";
import type { Id } from "../../convex/_generated/dataModel";

function message(error: unknown) { return error instanceof Error ? error.message : "Unable to save. Please try again."; }

export default function AccessGate({ children, onSignOut }: { children: ReactNode; onSignOut: () => Promise<void> }) {
  const { isAuthenticated } = useConvexAuth();
  const access = useQuery(api.access.current, isAuthenticated ? {} : "skip");
  const requestAccess = useMutation(api.access.requestAccess);
  const ensureWorkspace = useMutation(api.accounts.ensurePersonalWorkspace);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [manage, setManage] = useState(false);
  useEffect(() => {
    if (access?.status === "approved") void ensureWorkspace().catch(error => setError(message(error)));
  }, [access?.status, ensureWorkspace]);

  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try { await requestAccess({ reason }); } catch (error) { setError(message(error)); } finally { setBusy(false); }
  }

  if (access === undefined) return <div className="app-session-loading" role="status">Checking workspace access…</div>;
  if (access?.status === "approved") return <>
    {access.isAdmin && <div className="access-admin-bar"><span>DAISY owner</span><button className="pill pill-ghost" onClick={() => setManage(value => !value)}>{manage ? "Back to workspace" : "Manage access requests"}</button></div>}
    {error && <p className="auth-message error" role="alert">{error}</p>}
    {access.isAdmin && manage ? <AccessRequests /> : children}
  </>;

  const state = access?.status ?? "unrequested";
  return <main className="access-shell"><section className="auth-panel" aria-labelledby="access-title">
    <div className="auth-heading"><p>DAISY private preview</p><h2 id="access-title">{state === "pending" ? "Your request is pending." : state === "denied" ? "Access was not approved." : state === "revoked" ? "Workspace access has been revoked." : "Request workspace access."}</h2></div>
    <p className="access-description">{state === "unrequested" ? "DAISY is invite only. Submit a request and the owner will review it before you can use datasets, models or AI features." : "The owner reviews access for this account. This page updates automatically when your request is approved."}</p>
    <p className="access-description">Signed in as {access?.email || "your account"}</p>
    {state === "unrequested" && <form className="auth-form" onSubmit={submit}>
      <label><span>What would you like to use DAISY for? (optional)</span><textarea className="ws-input" maxLength={500} rows={4} value={reason} onChange={event => setReason(event.target.value)} /></label>
      <button className="auth-submit" disabled={busy}>{busy ? "Sending request…" : "Request access"}</button>
    </form>}
    {error && <p className="auth-message error" role="alert">{error}</p>}
    <button className="auth-back" onClick={() => { setError(""); void onSignOut().catch(error => setError(message(error))); }}>Sign out</button>
  </section></main>;
}

function AccessRequests() {
  const [filter, setFilter] = useState<"pending" | "approved" | "denied" | "revoked">("pending");
  const { results, status, loadMore } = usePaginatedQuery(api.access.listRequests, { status: filter }, { initialNumItems: 20 });
  const review = useMutation(api.access.review);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function decide(id: Id<"accessRequests">, status: "approved" | "denied" | "revoked") {
    setBusy(true); setError("");
    try { await review({ id, status }); } catch (error) { setError(message(error)); } finally { setBusy(false); }
  }
  return <main className="access-management">
    <h1>Workspace access</h1><p>Approve requests to let people use DAISY. Revoking access blocks subsequent API requests.</p>
    <label>Status <select className="ws-input" value={filter} onChange={event => setFilter(event.target.value as typeof filter)}>{["pending", "approved", "denied", "revoked"].map(value => <option key={value}>{value}</option>)}</select></label>
    {error && <p role="alert" className="auth-message error">{error}</p>}
    {status === "LoadingFirstPage" && <p role="status">Loading requests…</p>}
    {results.length === 0 && status !== "LoadingFirstPage" && <p>No {filter} requests.</p>}
    <ul className="access-request-list">{results.map(request => <li key={request._id}>
      <h2>{request.name || request.email}</h2><p>{request.email} · {request.emailVerified ? "Verified email" : "Unverified email — confirm the person's identity before approving"}</p><p>{request.reason || "No message provided."}</p>
      <p>Requested {new Date(request._creationTime).toLocaleDateString()}</p>
      <div className="access-actions">
        {request.status !== "approved" && <button className="pill pill-solid" disabled={busy} onClick={() => void decide(request._id, "approved")}>Approve</button>}
        {request.status === "pending" && <button className="pill pill-ghost" disabled={busy} onClick={() => void decide(request._id, "denied")}>Deny</button>}
        {request.status === "approved" && <button className="pill pill-ghost" disabled={busy} onClick={() => void decide(request._id, "revoked")}>Revoke</button>}
      </div>
    </li>)}</ul>
    {(status === "CanLoadMore" || status === "LoadingMore") && <button className="pill pill-ghost" disabled={status === "LoadingMore"} onClick={() => loadMore(20)}>Load more</button>}
  </main>;
}
