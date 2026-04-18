import React, { useRef } from "react";
import { useFrame } from "@react-three/fiber";

export default function Brain() {
    const mesh = useRef();

    useFrame(({ clock }) => {
        if (mesh.current) {
            mesh.current.rotation.y += 0.01;

            const scale = 1 + Math.sin(clock.getElapsedTime() * 2) * 0.05;
            mesh.current.scale.set(scale, scale, scale);
        }
    });

    return ( <
        > { /* Inner core */ } <
        mesh ref = { mesh } >
        <
        sphereGeometry args = {
            [1, 64, 64] }
        /> <
        meshStandardMaterial color = "#00ffff"
        emissive = "#00ffff"
        emissiveIntensity = { 3 }
        /> <
        /mesh>

        { /* Outer shell */ } <
        mesh >
        <
        sphereGeometry args = {
            [1.3, 64, 64] }
        /> <
        meshStandardMaterial color = "#00ffff"
        emissive = "#00ffff"
        emissiveIntensity = { 1 }
        wireframe transparent opacity = { 0.3 }
        /> <
        /mesh> <
        />
    );
}