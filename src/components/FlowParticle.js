import React, { useRef } from "react";
import { useFrame } from "@react-three/fiber";

export default function FlowParticle({ start, end }) {
    const mesh = useRef();
    const t = useRef(0);

    useFrame(() => {
        t.current += 0.015;

        if (t.current > 1) t.current = 0;

        const x = start[0] + (end[0] - start[0]) * t.current;
        const y = start[1] + (end[1] - start[1]) * t.current;
        const z = start[2] + (end[2] - start[2]) * t.current;

        if (mesh.current) {
            mesh.current.position.set(x, y, z);
        }
    });

    return ( <
        mesh ref = { mesh } >
        <
        sphereGeometry args = {
            [0.12, 16, 16]
        }
        /> <
        meshStandardMaterial color = "#00ffff"
        emissive = "#00ffff"
        emissiveIntensity = { 2 }
        /> < /
        mesh >
    );
}