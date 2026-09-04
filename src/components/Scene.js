import React, { useState, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, Line } from "@react-three/drei";
import { EffectComposer, Bloom } from "@react-three/postprocessing";

import Brain from "./Brain";
import AgentNode from "./AgentNode";
import FlowParticle from "./FlowParticle";
import ChatPanel from "./ChatPanel";
import ControlPanel from "./ControlPanel";
import AgentLogPanel from "./AgentLogPanel";
import PipelineTracker from "./PipelineTracker";
import TargetColumnSelector from "./TargetColumnSelector";

const API_BASE = "http://localhost:8000";

// Rotating Ring
function Ring() {
    const ref = useRef();

    useFrame(() => {
        if (ref.current) {
            ref.current.rotation.z += 0.01;
        }
    });

    return (
        <mesh ref={ref} rotation={[Math.PI / 2, 0, 0]}>
            <torusGeometry args={[2, 0.05, 16, 100]} />
            <meshStandardMaterial color="cyan" emissive="cyan" emissiveIntensity={1} />
        </mesh>
    );
}

export default function Scene() {
    const [activeNode, setActiveNode] = useState("Data");
    const [datasetId, setDatasetId] = useState(null);
    const [isRunning, setIsRunning] = useState(false);
    const [agentResult, setAgentResult] = useState(null);
    const [edaResult, setEdaResult] = useState(null);
    const [featureResult, setFeatureResult] = useState(null);
    const [modelSelectionResult, setModelSelectionResult] = useState(null);
    const [modelTrainingResult, setModelTrainingResult] = useState(null);
    const [agentError, setAgentError] = useState(null);
    const [pipelineStage, setPipelineStage] = useState("upload");


    async function runAgent(endpoint, body) {

        const res = await fetch(`${API_BASE}${endpoint}`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(body),
        });

        const data = await res.json();

        if (!res.ok) {
            throw new Error(data.detail || "Agent failed");
        }

        return data;
    }

    const handleRunCleaningAgent = async (dsId) => {
        setIsRunning(true);
        setAgentResult(null);
        setEdaResult(null);
        setFeatureResult(null);
        setModelSelectionResult(null);
        setModelTrainingResult(null);
        setAgentError(null);
        setActiveNode("Data");

        try {

            const cleaning = await runAgent(
                "/agents/data-cleaning",
                { dataset_id: dsId }
            );

            setAgentResult(cleaning);
            setPipelineStage("cleaning");
            // Was setActiveNode("Evaluation") here — lit a node for a
            // stage that doesn't exist yet in this pipeline. Now that
            // Feature/Model/Training are real nodes, this stays on
            // "Data" (the stage that actually just ran) instead.

        }
        catch (err) {

            setAgentError(err.message || "Something went wrong.");

        }
        finally {

            setIsRunning(false);

        }
    };

        const handleRunEDAAgent = async () => {

        if (!agentResult?.cleaned_dataset_id) return;

        setIsRunning(true);
        setActiveNode("Data"); // EDA also operates on the data domain — no separate node yet

        try {

            const eda = await runAgent(
                "/agents/eda",
                {
                    dataset_id: agentResult.cleaned_dataset_id
                }
            );

            setEdaResult(eda);
            setPipelineStage("eda");

        }
        catch (err) {

            setAgentError(err.message);

        }
        finally {

            setIsRunning(false);

        }

    };

    const handleRunFeatureEngineering = async () => {
        if (!agentResult?.cleaned_dataset_id) return;

        setIsRunning(true);
        setAgentError(null);
        setActiveNode("Feature");

        try {
            const feature = await runAgent(
                "/agents/feature-engineering",
                { dataset_id: agentResult.cleaned_dataset_id }
            );
            setFeatureResult(feature);
            setPipelineStage("feature");
        }
        catch (err) {
            setAgentError(err.message || "Feature engineering failed.");
        }
        finally {
            setIsRunning(false);
        }
    };

    const handleRunModelSelection = async (targetColumn) => {
        if (!featureResult?.engineered_dataset_id) return;

        setIsRunning(true);
        setAgentError(null);
        setActiveNode("Model");

        try {
            const selection = await runAgent(
                "/agents/model-selection",
                {
                    dataset_id: featureResult.engineered_dataset_id,
                    target_column: targetColumn,
                }
            );
            setModelSelectionResult(selection);
            setPipelineStage("model-selection");
        }
        catch (err) {
            setAgentError(err.message || "Model selection failed.");
        }
        finally {
            setIsRunning(false);
        }
    };

    const handleRunModelTraining = async (candidateModels) => {
        if (!featureResult?.engineered_dataset_id || !modelSelectionResult) return;

        setIsRunning(true);
        setAgentError(null);
        setActiveNode("Training");

        try {
            const training = await runAgent(
                "/agents/model-training",
                {
                    dataset_id: featureResult.engineered_dataset_id,
                    target_column: modelSelectionResult.input_summary.target_column,
                    candidate_models: candidateModels,
                }
            );
            setModelTrainingResult(training);
            setPipelineStage("model-training");
        }
        catch (err) {
            setAgentError(err.message || "Model training failed.");
        }
        finally {
            setIsRunning(false);
        }
    };

    return (
        <>
            {/* SAFE CANVAS */}
            {typeof window !== "undefined" && (
                <Canvas
                    style={{ position: "fixed", top: 0, left: 0, width: "100vw", height: "100vh", zIndex: 0 }}
                    camera={{ position: [0, 0, 5], fov: 70 }}
                    gl={{ antialias: true, powerPreference: "high-performance" }}
                >
                    {/* LIGHTING */}
                    <ambientLight intensity={0.6} />
                    <pointLight position={[5, 5, 5]} intensity={3} color="cyan" />
                    <pointLight position={[-5, -5, 5]} intensity={2} color="cyan" />

                    {/* CORE */}
                    <Brain />
                    <Ring />

                    {/* NODES */}
                    <AgentNode position={[3, 0, 0]} label="Data" active={activeNode === "Data"} />
                    <AgentNode position={[-3, 0, 0]} label="Model" active={activeNode === "Model"} />
                    <AgentNode position={[0, 3, 0]} label="Training" active={activeNode === "Training"} />
                    <AgentNode position={[0, -3, 0]} label="Evaluation" active={activeNode === "Evaluation"} />
                    <AgentNode position={[2.1, -2.1, 0]} label="Feature" active={activeNode === "Feature"} />

                    {/* CONNECTION LINES */}
                    <Line points={[[0, 0, 0], [3, 0, 0]]} color="white" />
                    <Line points={[[0, 0, 0], [-3, 0, 0]]} color="white" />
                    <Line points={[[0, 0, 0], [0, 3, 0]]} color="white" />
                    <Line points={[[0, 0, 0], [0, -3, 0]]} color="white" />
                    <Line points={[[0, 0, 0], [2.1, -2.1, 0]]} color="white" />

                    {/* FLOW PARTICLES */}
                    {activeNode === "Data" && (
                        <>
                            <FlowParticle start={[0, 0, 0]} end={[3, 0, 0]} />
                            <FlowParticle start={[0, 0, 0]} end={[3, 0, 0]} />
                        </>
                    )}
                    {activeNode === "Model" && (
                        <>
                            <FlowParticle start={[0, 0, 0]} end={[-3, 0, 0]} />
                            <FlowParticle start={[0, 0, 0]} end={[-3, 0, 0]} />
                        </>
                    )}
                    {activeNode === "Training" && (
                        <>
                            <FlowParticle start={[0, 0, 0]} end={[0, 3, 0]} />
                            <FlowParticle start={[0, 0, 0]} end={[0, 3, 0]} />
                        </>
                    )}
                    {activeNode === "Evaluation" && (
                        <>
                            <FlowParticle start={[0, 0, 0]} end={[0, -3, 0]} />
                            <FlowParticle start={[0, 0, 0]} end={[0, -3, 0]} />
                        </>
                    )}
                    {activeNode === "Feature" && (
                        <>
                            <FlowParticle start={[0, 0, 0]} end={[2.1, -2.1, 0]} />
                            <FlowParticle start={[0, 0, 0]} end={[2.1, -2.1, 0]} />
                        </>
                    )}

                    {/* CAMERA CONTROLS */}
                    <OrbitControls enablePan={false} minDistance={4} maxDistance={8} />

                    {/* BLOOM */}
                    <EffectComposer multisampling={0}>
                        <Bloom intensity={0.3} luminanceThreshold={0.4} luminanceSmoothing={0.8} />
                    </EffectComposer>
                </Canvas>
            )}

            {/* STATUS */}
            <div
                style={{
                    position: "fixed",
                    top: "20px",
                    left: "50%",
                    transform: "translateX(-50%)",
                    color: "#00ffff",
                    fontWeight: "bold",
                    background: "rgba(0,0,0,0.5)",
                    padding: "8px 20px",
                    borderRadius: "20px",
                    border: "1px solid rgba(0,255,255,0.3)"
                }}
            >
                System Status: Ready
            </div>

            {/* CONTROLS */}
            <ControlPanel
                onDatasetReady={(data) => {
                    setDatasetId(data.dataset_id);
                    setPipelineStage("cleaning");
                }}
                onRun={handleRunCleaningAgent}
                onRunEDA={handleRunEDAAgent}
                onRunFeatureEngineering={handleRunFeatureEngineering}
                canRunEDA={!!agentResult}
                canRunFeatureEngineering={!!agentResult}
                isRunning={isRunning}
                pipelineDone={!!agentResult}
            />

             {/* PIPELINE TRACKER */}
            {/* <PipelineTracker currentStage={pipelineStage} /> */}

            {/* TARGET COLUMN SELECTOR — appears once Feature Engineering
                has produced an engineered dataset to pick a target from */}
            {featureResult && !modelSelectionResult && (
                <TargetColumnSelector
                    columns={featureResult.output_summary?.columns_after || []}
                    onConfirm={handleRunModelSelection}
                    isRunning={isRunning}
                />
            )}

            {/* AGENT LOG */}
            <AgentLogPanel
                isRunning={isRunning}
                error={agentError}
                agentResult={agentResult}
                edaResult={edaResult}
                featureResult={featureResult}
                modelSelectionResult={modelSelectionResult}
                modelTrainingResult={modelTrainingResult}
                onTrainModels={handleRunModelTraining}
            />

        

            {/* CHAT */}
            <ChatPanel setActiveNode={setActiveNode} datasetId={datasetId} />
        </>
    );
}
