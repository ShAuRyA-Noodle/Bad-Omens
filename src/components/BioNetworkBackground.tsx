import { useRef, useMemo } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";

const ParticleSwarm = () => {
  const count = 1200; // Reduced from 3000 - keeps the aesthetic without obscuring text
  const meshRef = useRef<THREE.InstancedMesh>(null);

  const dummy = useMemo(() => new THREE.Object3D(), []);

  // Generate random particles in a massive sphere
  const particles = useMemo(() => {
    const temp = [];
    for (let i = 0; i < count; i++) {
      const radius = 25;
      const u = Math.random();
      const v = Math.random();
      const theta = 2 * Math.PI * u;
      const phi = Math.acos(2 * v - 1);

      const r = Math.cbrt(Math.random()) * radius;

      const x = r * Math.sin(phi) * Math.cos(theta);
      const y = r * Math.sin(phi) * Math.sin(theta);
      const z = r * Math.cos(phi);

      temp.push({
        t: Math.random() * 100,
        factor: 20 + Math.random() * 100,
        speed: 0.01 + Math.random() / 200,
        xFactor: 2 + Math.random() * 2,
        yFactor: 2 + Math.random() * 2,
        zFactor: 2 + Math.random() * 2,
        baseX: x,
        baseY: y,
        baseZ: z,
        currentX: x,
        currentY: y,
        currentZ: z
      });
    }
    return temp;
  }, [count]);

  const { camera } = useThree();

  useFrame((state) => {
    if (!meshRef.current) return;

    // Convert normalized device coordinates (state.pointer) to world space
    // to find where the mouse is in the 3D scene (approximately at z=0)
    const mouseVector = new THREE.Vector3(state.pointer.x, state.pointer.y, 0.5);
    mouseVector.unproject(camera);
    mouseVector.sub(camera.position).normalize();
    const distance = -camera.position.z / mouseVector.z;
    const mousePos = new THREE.Vector3().copy(camera.position).add(mouseVector.multiplyScalar(distance));

    particles.forEach((particle, i) => {
      let { t } = particle;
      const { factor, speed, xFactor, yFactor, zFactor, baseX, baseY, baseZ } = particle;

      // Slowly drift the base position over time
      t = particle.t += speed / 2;
      const xNoise = Math.sin(t) * xFactor;
      const yNoise = Math.cos(t) * yFactor;
      const zNoise = Math.sin(t) * zFactor;

      let targetX = baseX + xNoise;
      let targetY = baseY + yNoise;
      const targetZ = baseZ + zNoise;

      // Mouse interaction: Repel particles
      const dx = targetX - mousePos.x;
      const dy = targetY - mousePos.y;
      // We only care about x,y plane for mouse repel mainly
      const distToMouse = Math.sqrt(dx * dx + dy * dy);

      const repelRadius = 8;
      if (distToMouse < repelRadius) {
        const force = (repelRadius - distToMouse) / repelRadius;
        targetX += (dx / distToMouse) * force * 5;
        targetY += (dy / distToMouse) * force * 5;
      }

      // Smoothly interpolate current position toward target position
      particle.currentX += (targetX - particle.currentX) * 0.1;
      particle.currentY += (targetY - particle.currentY) * 0.1;
      particle.currentZ += (targetZ - particle.currentZ) * 0.1;

      dummy.position.set(particle.currentX, particle.currentY, particle.currentZ);

      // Determine color based on depth
      // Further back = primary (neon green), closer = secondary (neon cyan)
      // mapped roughly from z = -20 to z = 20
      dummy.updateMatrix();
      meshRef.current!.setMatrixAt(i, dummy.matrix);

      // We just use a single material color for performance, but you could use instanceColor
    });

    meshRef.current.instanceMatrix.needsUpdate = true;

    // Slowly rotate the entire swarm
    meshRef.current.rotation.y += 0.001;
    meshRef.current.rotation.x += 0.0005;
  });

  return (
    <instancedMesh ref={meshRef} args={[undefined, undefined, count]}>
      <sphereGeometry args={[0.05, 4, 4]} />
      <meshBasicMaterial color="#39FF14" transparent opacity={0.25} blending={THREE.AdditiveBlending} depthWrite={false} />
    </instancedMesh>
  );
};

export const BioNetworkBackground = () => {
  return (
    <div className="fixed inset-0 z-[-1] pointer-events-none bg-transparent" style={{ mixBlendMode: 'screen' }}>
      {/* Background canvas container - pointer events none so it doesn't block UI clicks */}
      <Canvas
        camera={{ position: [0, 0, 30], fov: 60 }}
        gl={{ antialias: false, alpha: true }}
        dpr={[1, 2]} // Performance optimization
      >
        <fog attach="fog" args={["#000000", 10, 50]} />
        <ParticleSwarm />
      </Canvas>
    </div>
  );
};
