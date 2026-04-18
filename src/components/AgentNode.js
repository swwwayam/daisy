import React, { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { Text } from "@react-three/drei";

export default function AgentNode({ position, active, label, onClick }) {
    const mesh = useRef();

    useFrame(({ clock }) => {
        if (mesh.current && active) {
            const scale = 1 + Math.sin(clock.getElapsedTime() * 3) * 0.2;
            mesh.current.scale.set(scale, scale, scale);
        }
    });

    return ( <
        group position = { position } >
        <
        mesh ref = { mesh }
        onClick = { onClick } >
        <
        sphereGeometry args = {
            [0.5, 32, 32]
        }
        /> <
        meshStandardMaterial color = { active ? "#00ffff" : "#555" }
        emissive = { active ? "#00ffff" : "black" }
        emissiveIntensity = { active ? 2.5 : 0 }
        /> < /
        mesh >

        <
        Text position = {
            [0, -1.2, 0]
        }
        fontSize = { 0.6 }
        color = { active ? "#00ffff" : "white" }
        anchorX = "center"
        anchorY = "middle"
        outlineWidth = { 0.02 }
        outlineColor = "black" > { label } <
        /Text> < /
        group >
    );
}