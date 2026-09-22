import { useEffect, useRef, useState, type MutableRefObject } from "react";

export interface ScenePose {
  morph: number;
  spread: number;
  x: number;
  y: number;
  scale: number;
  rotation: number;
  opacity: number;
}

export default function ParticleScene({ pose, paused }: { pose: MutableRefObject<ScenePose>; paused: boolean }) {
  const mount = useRef<HTMLDivElement>(null);
  const stopped = useRef(paused);
  const [unavailable, setUnavailable] = useState(false);
  useEffect(() => { stopped.current = paused; }, [paused]);

  useEffect(() => {
    const host = mount.current;
    if (!host) return;
    let disposed = false;
    let cleanup = () => {};
    // Load WebGL separately so the readable page is available immediately.
    import("three").then((THREE) => {
      if (disposed) return;
      let renderer: InstanceType<typeof THREE.WebGLRenderer>;
      try {
        renderer = new THREE.WebGLRenderer({ alpha: true, antialias: false, powerPreference: "low-power" });
      } catch {
        setUnavailable(true);
        return;
      }
      renderer.setClearColor(0x000000, 0);
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.6));
      renderer.domElement.setAttribute("aria-hidden", "true");
      host.appendChild(renderer.domElement);
      const scene = new THREE.Scene();
      const camera = new THREE.PerspectiveCamera(40, 1, .1, 100);
      camera.position.z = 9;
      const mobile = window.innerWidth < 768;
      const count = mobile ? 4000 : 9500;
      const network = new Float32Array(count * 3);
      const networkIntensity = new Float32Array(count);
      const sphere = new Float32Array(count * 3);
      const helix = new Float32Array(count * 3);
      const ring = new Float32Array(count * 3);
      const scatter = new Float32Array(count * 3);
      const colors = new Float32Array(count * 3);
      const seeds = new Float32Array(count);
      let seed = 73;
      const random = () => { seed = (seed * 16807) % 2147483647; return (seed - 1) / 2147483646; };
      const palette = ["#ffb829", "#8052ff", "#f1e9ff", "#ffb829", "#9a76ff", "#51cbb0", "#e26da6", "#c8c8de"].map(c => new THREE.Color(c));

      // An input-to-output network: distinct layers, spherical nodes, and data paths.
      const layers = [3, 5, 6, 5, 2].map((size, layer) =>
        Array.from({ length: size }, (_, index) => new THREE.Vector3(
          (layer - 2) * .88,
          (index - (size - 1) / 2) * .55,
          Math.sin(index * 1.7 + layer * .9) * .28,
        )),
      );
      const nodes = layers.flat();
      const edges: [InstanceType<typeof THREE.Vector3>, InstanceType<typeof THREE.Vector3>][] = [];
      layers.slice(0, -1).forEach((layer, index) => {
        layer.forEach(from => layers[index + 1].forEach(to => edges.push([from, to])));
      });

      for (let i = 0; i < count; i++) {
        const k = i * 3;
        const theta = random() * Math.PI * 2;
        const phi = Math.acos(2 * random() - 1);
        const sx = Math.sin(phi) * Math.cos(theta);
        const sy = Math.cos(phi);
        const sz = Math.sin(phi) * Math.sin(theta);
        const isNode = i % 5 !== 0;
        if (isNode) {
          const node = nodes[i % nodes.length];
          const radius = .115 + random() * .035;
          network[k] = node.x + sx * radius;
          network[k + 1] = node.y + sy * radius;
          network[k + 2] = node.z + sz * radius;
        } else {
          const [from, to] = edges[i % edges.length];
          const progress = random();
          network[k] = from.x + (to.x - from.x) * progress;
          network[k + 1] = from.y + (to.y - from.y) * progress;
          network[k + 2] = from.z + (to.z - from.z) * progress;
        }
        networkIntensity[i] = isNode ? .7 : .16;
        sphere[k] = sx * 1.64; sphere[k + 1] = sy * 1.64; sphere[k + 2] = sz * 1.64;
        const angle = (i / count) * Math.PI * 14;
        const strand = i % 2 === 0 ? 0 : Math.PI;
        const radius = .88 + random() * .22;
        helix[k] = Math.cos(angle + strand) * radius;
        helix[k + 1] = (i / count - .5) * 3.7;
        helix[k + 2] = Math.sin(angle + strand) * radius;
        const a = random() * Math.PI * 2;
        const b = random() * Math.PI * 2;
        const tube = .27 + random() * .1;
        ring[k] = (1.35 + tube * Math.cos(b)) * Math.cos(a);
        ring[k + 1] = (1.35 + tube * Math.cos(b)) * Math.sin(a);
        ring[k + 2] = tube * Math.sin(b);
        scatter[k] = (random() - .5) * 2.7;
        scatter[k + 1] = (random() - .5) * 2.7;
        scatter[k + 2] = random() * 2 - 1;
        const color = palette[Math.floor(random() * palette.length)];
        colors[k] = color.r; colors[k + 1] = color.g; colors[k + 2] = color.b;
        seeds[i] = random();
      }

      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute("position", new THREE.BufferAttribute(network, 3));
      geometry.setAttribute("aNetworkIntensity", new THREE.BufferAttribute(networkIntensity, 1));
      geometry.setAttribute("aSphere", new THREE.BufferAttribute(sphere, 3));
      geometry.setAttribute("aHelix", new THREE.BufferAttribute(helix, 3));
      geometry.setAttribute("aRing", new THREE.BufferAttribute(ring, 3));
      geometry.setAttribute("aScatter", new THREE.BufferAttribute(scatter, 3));
      geometry.setAttribute("aColor", new THREE.BufferAttribute(colors, 3));
      geometry.setAttribute("aSeed", new THREE.BufferAttribute(seeds, 1));
      const uniforms = {
        uTime: { value: 0 }, uMorph: { value: 0 }, uSpread: { value: 0 },
        uOpacity: { value: 1 }, uPixelRatio: { value: renderer.getPixelRatio() },
        uAspect: { value: 1 },
      };
      const material = new THREE.ShaderMaterial({
        uniforms, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
        vertexShader: `
          attribute vec3 aSphere; attribute vec3 aHelix; attribute vec3 aRing;
          attribute vec3 aScatter; attribute vec3 aColor; attribute float aSeed; attribute float aNetworkIntensity;
          uniform float uTime; uniform float uMorph; uniform float uSpread; uniform float uPixelRatio; uniform float uAspect;
          varying vec3 vColor; varying float vAlpha; varying float vAngle;
          void main() {
            vec3 p = mix(position, aSphere, smoothstep(0.0, 1.0, uMorph));
            p = mix(p, aHelix, smoothstep(1.0, 2.0, uMorph));
            p = mix(p, aRing, smoothstep(2.0, 3.0, uMorph));
            p += vec3(sin(uTime*.35+aSeed*60.0), cos(uTime*.25+aSeed*30.0), sin(uTime*.3+aSeed*80.0))*.014;
            vec4 mv = modelViewMatrix * vec4(p, 1.0);
            // Drift in camera space, independent of the sculpture's location/rotation.
            // Wrap beyond the viewport so particles keep flowing during a scroll pause.
            vec2 velocity = vec2(.035 + aSeed * .035, .025 * sin(aSeed * 30.0));
            vec2 drift = mod(aScatter.xy + velocity * uTime + 1.35, 2.7) - 1.35;
            drift += vec2(sin(uTime*.32+aSeed*40.0), cos(uTime*.28+aSeed*50.0)) * .065;
            float depth = 8.0 + aScatter.z * 2.0 + sin(uTime*.2+aSeed*20.0)*.35;
            vec3 field = vec3(drift * vec2(uAspect, 1.0) * depth * .3639702, -depth);
            mv.xyz = mix(mv.xyz, field, uSpread);
            gl_Position = projectionMatrix * mv;
            float foreground = 1.0 + uSpread * pow(aSeed, 180.0) * 6.0;
            gl_PointSize = clamp((2.7+aSeed*3.5)*foreground*uPixelRatio*(7.0/-mv.z), 1.5, mix(14.0, 36.0, uSpread));
            vColor = aColor;
            vAlpha = mix(.5, 1.0, smoothstep(-1.5, 1.5, p.z)) * (.8 + .2*sin(aSeed*45.0+uTime*.35));
            vAlpha *= mix(aNetworkIntensity, 1.0, max(uSpread, smoothstep(0.0, 1.0, uMorph)));
            vAngle = aSeed*6.283 + uTime*.04;
          }`,
        fragmentShader: `
          uniform float uOpacity;
          varying vec3 vColor; varying float vAlpha; varying float vAngle;
          float edge(vec2 p, vec2 a, vec2 b) {
            vec2 pa = p-a; vec2 ba = b-a;
            return length(pa-ba*clamp(dot(pa,ba)/dot(ba,ba),0.0,1.0));
          }
          void main() {
            vec2 p = gl_PointCoord-.5;
            p = mat2(cos(vAngle),-sin(vAngle),sin(vAngle),cos(vAngle))*p;
            float d = min(edge(p,vec2(0.,.4),vec2(-.35,-.22)),min(edge(p,vec2(-.35,-.22),vec2(.35,-.22)),edge(p,vec2(.35,-.22),vec2(0.,.4))));
            float alpha = 1.0-smoothstep(.035,.13,d);
            if (alpha < .01) discard;
            gl_FragColor = vec4(vColor * 1.25, alpha*vAlpha*uOpacity);
          }`,
      });
      const cloud = new THREE.Points(geometry, material);
      cloud.frustumCulled = false;
      scene.add(cloud);

      const connectionsGeometry = new THREE.BufferGeometry().setFromPoints(edges.flat());
      const connectionsMaterial = new THREE.LineBasicMaterial({ color: "#9a76ff", transparent: true, opacity: .22, depthWrite: false, blending: THREE.AdditiveBlending });
      const connections = new THREE.LineSegments(connectionsGeometry, connectionsMaterial);
      const signalsGeometry = new THREE.BufferGeometry();
      signalsGeometry.setAttribute("position", new THREE.Float32BufferAttribute(edges.flatMap(([from]) => from.toArray()), 3));
      signalsGeometry.setAttribute("aDestination", new THREE.Float32BufferAttribute(edges.flatMap(([, to]) => to.toArray()), 3));
      signalsGeometry.setAttribute("aPhase", new THREE.Float32BufferAttribute(edges.map((_, i) => (i * .618) % 1), 1));
      const signalsMaterial = new THREE.ShaderMaterial({
        transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
        uniforms: { uTime: uniforms.uTime, uOpacity: { value: 1 }, uPixelRatio: uniforms.uPixelRatio },
        vertexShader: `
          attribute vec3 aDestination; attribute float aPhase;
          uniform float uTime; uniform float uPixelRatio;
          varying float vProgress;
          void main() {
            vProgress = fract(uTime * .22 + aPhase);
            vec4 mv = modelViewMatrix * vec4(mix(position, aDestination, vProgress), 1.0);
            gl_Position = projectionMatrix * mv;
            gl_PointSize = 5.5 * uPixelRatio * (7.0 / -mv.z);
          }`,
        fragmentShader: `
          uniform float uOpacity; varying float vProgress;
          void main() {
            float glow = 1.0 - smoothstep(.05, .5, length(gl_PointCoord - .5));
            float envelope = smoothstep(0.0, .12, vProgress) * (1.0 - smoothstep(.88, 1.0, vProgress));
            gl_FragColor = vec4(1.0, .72, .3, glow * envelope * uOpacity);
          }`,
      });
      const signals = new THREE.Points(signalsGeometry, signalsMaterial);
      signals.frustumCulled = false;
      const networkDetails = new THREE.Group();
      networkDetails.add(connections, signals);
      scene.add(networkDetails);

      // Sparse background fragments remain independent of the central sculpture.
      const ambientGeometry = new THREE.BufferGeometry();
      const ambientPositions = new Float32Array(180 * 3);
      for (let i = 0; i < ambientPositions.length; i += 3) {
        ambientPositions[i] = (random() - .5) * 18;
        ambientPositions[i + 1] = (random() - .5) * 10;
        ambientPositions[i + 2] = -2 - random() * 4;
      }
      ambientGeometry.setAttribute("position", new THREE.BufferAttribute(ambientPositions, 3));
      const ambientMaterial = new THREE.PointsMaterial({ color: "#aa8eff", size: .018, transparent: true, opacity: .35, depthWrite: false });
      const ambient = new THREE.Points(ambientGeometry, ambientMaterial);
      scene.add(ambient);

      const pointer = { x: 0, y: 0 };
      const smoothed = { x: 0, y: 0 };
      function onPointer(event: PointerEvent) {
        if (event.pointerType !== "mouse") return;
        pointer.x = (event.clientX / window.innerWidth - .5) * .45;
        pointer.y = (event.clientY / window.innerHeight - .5) * .3;
      }
      const resize = () => {
        const width = host.clientWidth; const height = host.clientHeight;
        camera.aspect = width / Math.max(height, 1);
        uniforms.uAspect.value = camera.aspect;
        camera.updateProjectionMatrix(); renderer.setSize(width, height);
      };
      const observer = new ResizeObserver(resize); observer.observe(host); resize();
      window.addEventListener("pointermove", onPointer, { passive: true });
      let previous = 0; let elapsed = 0; let lastPose = "";
      const displayed = { ...pose.current };
      const render = (now: number) => {
        if (disposed) return;
        const delta = Math.min((now - previous) / 1000, .05); previous = now;
        if (document.hidden) return;
        const smoothing = stopped.current ? 1 : 1 - Math.exp(-delta * 12);
        for (const key of Object.keys(displayed) as (keyof ScenePose)[]) displayed[key] += (pose.current[key] - displayed[key]) * smoothing;
        const state = displayed;
        host.style.visibility = state.opacity < .005 ? "hidden" : "visible";
        if (state.opacity < .005) return;
        if (!stopped.current) elapsed += delta;
        // Paused/reduced motion draws only when the layout or scroll pose changes.
        const poseKey = `${state.x},${state.y},${state.morph},${state.opacity},${state.scale},${state.rotation},${state.spread},${camera.aspect}`;
        if (stopped.current && lastPose === poseKey) return;
        lastPose = poseKey;
        smoothed.x += ((stopped.current ? 0 : pointer.x) - smoothed.x) * .035;
        smoothed.y += ((stopped.current ? 0 : pointer.y) - smoothed.y) * .035;
        uniforms.uTime.value = elapsed;
        uniforms.uMorph.value = state.morph;
        uniforms.uSpread.value = state.spread;
        uniforms.uOpacity.value = state.opacity;
        cloud.position.set(state.x, state.y, 0);
        cloud.scale.setScalar(state.scale);
        cloud.rotation.set(-.08 + smoothed.y, state.rotation + smoothed.x + Math.sin(elapsed * .13) * .16, -.13 + Math.sin(elapsed * .1) * .035);
        networkDetails.position.copy(cloud.position);
        networkDetails.quaternion.copy(cloud.quaternion);
        networkDetails.scale.copy(cloud.scale);
        const networkOpacity = (1 - THREE.MathUtils.smoothstep(state.morph, 0, .65)) * (1 - state.spread) * state.opacity;
        networkDetails.visible = networkOpacity > .005;
        connectionsMaterial.opacity = networkOpacity * .22;
        signalsMaterial.uniforms.uOpacity.value = networkOpacity;
        ambient.rotation.z = elapsed * .003;
        ambientMaterial.opacity = state.opacity * .3;
        renderer.render(scene, camera);
      }
      renderer.setAnimationLoop(render);
      const contextLost = (event: Event) => { event.preventDefault(); setUnavailable(true); renderer.setAnimationLoop(null); };
      renderer.domElement.addEventListener("webglcontextlost", contextLost);
      cleanup = () => {
        renderer.setAnimationLoop(null); observer.disconnect(); window.removeEventListener("pointermove", onPointer);
        renderer.domElement.removeEventListener("webglcontextlost", contextLost);
        geometry.dispose(); material.dispose(); ambientGeometry.dispose(); ambientMaterial.dispose();
        connectionsGeometry.dispose(); connectionsMaterial.dispose(); signalsGeometry.dispose(); signalsMaterial.dispose();
        renderer.dispose(); renderer.domElement.remove();
      };
    }).catch(() => { if (!disposed) setUnavailable(true); });
    return () => { disposed = true; cleanup(); };
  }, [pose]);

  return <div className="particle-scene" ref={mount} aria-hidden="true" data-unavailable={unavailable || undefined}>{unavailable && <div className="scene-fallback">{Array.from({ length: 60 }, (_, i) => <i key={i} style={{ left: `${48 + Math.sin(i * 2.4) * 25}%`, top: `${50 + Math.cos(i * 3.3) * 30}%`, color: ["#8052ff", "#ffb829", "#51cbb0"][i % 3] }}>△</i>)}</div>}</div>;
}
