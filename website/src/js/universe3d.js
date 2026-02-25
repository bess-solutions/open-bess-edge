/**
 * ═══════════════════════════════════════════════════════════
 *  BESS Solutions — 3D Neural Energy Universe
 *  ES Module · Three.js r157 + UnrealBloomPass + Vignette
 *
 *  Cargado como <script type="module"> desde index.html.
 *  Todos los addons se resuelven via importmap.
 *
 *  ► Para tunar el efecto, edita el objeto CONFIG.
 * ═══════════════════════════════════════════════════════════
 */

import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { GammaCorrectionShader } from 'three/addons/shaders/GammaCorrectionShader.js';

/* ──────────────────────────────────────────────────────────
   CONFIG — todos los parámetros en un solo lugar
   ────────────────────────────────────────────────────────── */
const CONFIG = {
    // ── Bloom ─────────────────────────────────────────────
    bloomStrength: 1.6,    // intensidad del glow (0 = ninguno, 3 = máximo)
    bloomRadius: 0.55,   // radio de dispersión del bloom
    bloomThreshold: 0.0,    // umbral de luminancia para activar bloom

    // ── Stars ──────────────────────────────────────────────
    starCount: 7000,
    starSpread: 400,
    starSize: 0.09,
    starOpacity: 0.45,
    starColor: 0x8bb8cc,

    // ── Energy Field A (verde — energía principal) ─────────
    energyACount: 4000,   // partículas
    energyARadius: 1.6,    // radio de la nube esférica (unidades scene)
    energyAColor: 0x10b981, // Emerald
    energyASize: 0.018,
    energyARotX: -0.07,  // velocidad rot X
    energyARotY: -0.05,  // velocidad rot Y

    // ── Energy Field B (azul — datos / red) ───────────────
    energyBCount: 1500,
    energyBRadius: 2.8,    // nube más dispersa
    energyBColor: 0x3b82f6, // Blue
    energyBSize: 0.012,
    energyBRotX: 0.04,
    energyBRotY: 0.025,

    // ── Planet ────────────────────────────────────────────
    planetRadius: 1.1,
    planetSegments: 64,
    planetColor: 0x0d2a3e,
    planetAtmColor: 0x22d3ee,
    planetAtmOpacity: 0.12,
    planetOffsetX: 0.65,   // desplazamiento a la derecha (fracción del ancho)
    planetRotSpeed: 0.0006,
    cloudCount: 3000,
    cloudColor: 0x1a5a7a,
    cloudSize: 0.005,
    cloudOpacity: 0.55,

    // ── BESS node network ─────────────────────────────────
    nodeCount: 14,
    nodeRadiusMin: 1.45,
    nodeRadiusMax: 2.1,
    nodeColor: 0x22d3ee,
    nodeSphereSize: 0.018,
    haloColor: 0x0891b2,
    haloSize: 0.045,
    connDist: 1.6,
    connColor: 0x0c3d52,
    packetCount: 10,
    packetColor: 0x22d3ee,
    packetSize: 0.010,
    packetSpeedMin: 0.003,
    packetSpeedMax: 0.008,

    // ── Camera ────────────────────────────────────────────
    cameraFov: 60,
    cameraZ: 3.5,
    cameraY: 0.2,

    // ── Animation ─────────────────────────────────────────
    networkRotY: 0.04,   // velocidad de rotación de la red
    animStep: 0.003,
    haloSpeedMin: 1.0,
    haloSpeedMax: 2.0,
    parallaxX: 0.4,
    parallaxY: 0.2,
    parallaxLerp: 0.035,

    // ── Float (campo de energía — oscilación suave) ───────
    floatAmpX: 0.08,   // amplitud oscilación
    floatAmpY: 0.06,
    floatFreqX: 0.4,
    floatFreqY: 0.6,
};

/* ──────────────────────────────────────────────────────────
   Canvas
   ────────────────────────────────────────────────────────── */
const canvas = document.getElementById('bess-universe');
if (!canvas) throw new Error('Canvas #bess-universe no encontrado');

/* ──────────────────────────────────────────────────────────
   Renderer
   ────────────────────────────────────────────────────────── */
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setClearColor(0x000000, 1);
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1;

/* ──────────────────────────────────────────────────────────
   Scene & Camera
   ────────────────────────────────────────────────────────── */
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(CONFIG.cameraFov, 1, 0.01, 500);
camera.position.set(0, CONFIG.cameraY, CONFIG.cameraZ);
camera.lookAt(0, 0, 0);

function resize() {
    const w = canvas.parentElement?.offsetWidth || window.innerWidth;
    const h = canvas.parentElement?.offsetHeight || window.innerHeight;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    composer.setSize(w, h);
    bloomPass.resolution.set(w, h);
}

/* ──────────────────────────────────────────────────────────
   Post-processing: EffectComposer + UnrealBloom + Gamma
   ────────────────────────────────────────────────────────── */
const composer = new EffectComposer(renderer);
const renderPass = new RenderPass(scene, camera);
composer.addPass(renderPass);

const bloomPass = new UnrealBloomPass(
    new THREE.Vector2(window.innerWidth, window.innerHeight),
    CONFIG.bloomStrength,
    CONFIG.bloomRadius,
    CONFIG.bloomThreshold
);
composer.addPass(bloomPass);

const gammaPass = new ShaderPass(GammaCorrectionShader);
gammaPass.renderToScreen = true;
composer.addPass(gammaPass);

/* ──────────────────────────────────────────────────────────
   Helpers
   ────────────────────────────────────────────────────────── */
function randomInSphere(count, radius) {
    const arr = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
        const theta = Math.random() * Math.PI * 2;
        const phi = Math.acos(2 * Math.random() - 1);
        const r = Math.cbrt(Math.random()) * radius; // distribución uniforme en volumen
        arr[i * 3] = r * Math.sin(phi) * Math.cos(theta);
        arr[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
        arr[i * 3 + 2] = r * Math.cos(phi);
    }
    return arr;
}

function randomOnSphere(count, radius) {
    const arr = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
        const theta = Math.random() * Math.PI * 2;
        const phi = Math.acos(2 * Math.random() - 1);
        const r = radius + Math.random() * 0.03;
        arr[i * 3] = r * Math.sin(phi) * Math.cos(theta);
        arr[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
        arr[i * 3 + 2] = r * Math.cos(phi);
    }
    return arr;
}

function makePoints(positions, color, size, opacity = 1) {
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    const mat = new THREE.PointsMaterial({
        color,
        size,
        transparent: true,
        opacity,
        sizeAttenuation: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
    });
    return new THREE.Points(geo, mat);
}

/* ──────────────────────────────────────────────────────────
   Stars (fondo estático)
   ────────────────────────────────────────────────────────── */
const starPos = new Float32Array(CONFIG.starCount * 3);
for (let i = 0; i < CONFIG.starCount * 3; i++) {
    starPos[i] = (Math.random() - 0.5) * CONFIG.starSpread;
}
scene.add(makePoints(starPos, CONFIG.starColor, CONFIG.starSize, CONFIG.starOpacity));

/* ──────────────────────────────────────────────────────────
   Energy Field A — verde (campo principal)
   ────────────────────────────────────────────────────────── */
const energyGroupA = new THREE.Group();
energyGroupA.rotation.z = Math.PI / 4; // mismo que R3F example
scene.add(energyGroupA);
const energyA = makePoints(
    randomInSphere(CONFIG.energyACount, CONFIG.energyARadius),
    CONFIG.energyAColor, CONFIG.energyASize
);
energyGroupA.add(energyA);

/* ──────────────────────────────────────────────────────────
   Energy Field B — azul (data stream)
   ────────────────────────────────────────────────────────── */
const energyGroupB = new THREE.Group();
energyGroupB.rotation.z = Math.PI / 4;
scene.add(energyGroupB);
const energyB = makePoints(
    randomInSphere(CONFIG.energyBCount, CONFIG.energyBRadius),
    CONFIG.energyBColor, CONFIG.energyBSize
);
energyGroupB.add(energyB);

/* ──────────────────────────────────────────────────────────
   Planet group
   ────────────────────────────────────────────────────────── */
const planetGroup = new THREE.Group();
// Se posiciona horizontalmente en el hero (se actualiza en resize)
scene.add(planetGroup);

// Core
const planetMesh = new THREE.Mesh(
    new THREE.SphereGeometry(CONFIG.planetRadius, CONFIG.planetSegments, CONFIG.planetSegments),
    new THREE.MeshBasicMaterial({ color: CONFIG.planetColor })
);
planetGroup.add(planetMesh);

// Atmósfera
planetGroup.add(new THREE.Mesh(
    new THREE.SphereGeometry(CONFIG.planetRadius * 1.06, 32, 32),
    new THREE.MeshBasicMaterial({
        color: CONFIG.planetAtmColor, transparent: true,
        opacity: CONFIG.planetAtmOpacity, side: THREE.FrontSide,
    })
));

// Nube de superficie
planetGroup.add(makePoints(
    randomOnSphere(CONFIG.cloudCount, CONFIG.planetRadius),
    CONFIG.cloudColor, CONFIG.cloudSize, CONFIG.cloudOpacity
));

/* ──────────────────────────────────────────────────────────
   BESS node network (orbita el planeta)
   ────────────────────────────────────────────────────────── */
const netRoot = new THREE.Group();
const nodeMat = new THREE.MeshBasicMaterial({ color: CONFIG.nodeColor });
const localPos = [];
const haloMats = [];
const haloSpeeds = [];

for (let i = 0; i < CONFIG.nodeCount; i++) {
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);
    const r = CONFIG.nodeRadiusMin + Math.random() * (CONFIG.nodeRadiusMax - CONFIG.nodeRadiusMin);
    const x = r * Math.sin(phi) * Math.cos(theta);
    const y = r * Math.sin(phi) * Math.sin(theta) * 0.55;
    const z = r * Math.cos(phi);
    localPos.push(new THREE.Vector3(x, y, z));

    const core = new THREE.Mesh(
        new THREE.SphereGeometry(CONFIG.nodeSphereSize, 8, 8), nodeMat
    );
    core.position.set(x, y, z);
    netRoot.add(core);

    const hm = new THREE.MeshBasicMaterial({
        color: CONFIG.haloColor, transparent: true, opacity: 0.12,
    });
    haloMats.push(hm);
    haloSpeeds.push(CONFIG.haloSpeedMin + Math.random() * (CONFIG.haloSpeedMax - CONFIG.haloSpeedMin));

    const halo = new THREE.Mesh(
        new THREE.SphereGeometry(CONFIG.haloSize, 8, 8), hm
    );
    halo.position.set(x, y, z);
    netRoot.add(halo);
}

// Conexiones
const connPairs = [];
for (let i = 0; i < CONFIG.nodeCount; i++) {
    for (let j = i + 1; j < CONFIG.nodeCount; j++) {
        const d = localPos[i].distanceTo(localPos[j]);
        if (d < CONFIG.connDist) {
            connPairs.push({ i, j, d });
            netRoot.add(new THREE.Line(
                new THREE.BufferGeometry().setFromPoints([localPos[i], localPos[j]]),
                new THREE.LineBasicMaterial({
                    color: CONFIG.connColor, transparent: true,
                    opacity: Math.max(0.1, 0.45 - d / CONFIG.connDist * 0.35),
                })
            ));
        }
    }
}

// Energy packets
const packetMesh = new THREE.Mesh(
    new THREE.SphereGeometry(CONFIG.packetSize, 5, 5),
    new THREE.MeshBasicMaterial({ color: CONFIG.packetColor })
);
const packets = [];
const activePairs = connPairs.slice(0, Math.min(CONFIG.packetCount, connPairs.length));
for (const pair of activePairs) {
    const m = packetMesh.clone();
    netRoot.add(m);
    packets.push({
        mesh: m,
        from: localPos[pair.i], to: localPos[pair.j],
        t: Math.random(),
        speed: CONFIG.packetSpeedMin + Math.random() * (CONFIG.packetSpeedMax - CONFIG.packetSpeedMin),
        dir: Math.random() > 0.5 ? 1 : -1,
    });
}

planetGroup.add(netRoot);

/* ──────────────────────────────────────────────────────────
   Mouse parallax
   ────────────────────────────────────────────────────────── */
let mx = 0, my = 0;
document.addEventListener('mousemove', e => {
    mx = (e.clientX / window.innerWidth - 0.5) * 2;
    my = (e.clientY / window.innerHeight - 0.5) * 2;
}, { passive: true });

/* ──────────────────────────────────────────────────────────
   Planet horizontal position based on viewport
   ────────────────────────────────────────────────────────── */
function updatePlanetPosition() {
    const aspect = camera.aspect;
    const vFovRad = (CONFIG.cameraFov * Math.PI) / 180;
    const halfH = Math.tan(vFovRad / 2) * CONFIG.cameraZ;
    const halfW = halfH * aspect;
    // Planeta centrado 65% hacia la derecha
    planetGroup.position.x = halfW * CONFIG.planetOffsetX;
    planetGroup.position.y = 0;
}

/* ──────────────────────────────────────────────────────────
   Animation loop
   ────────────────────────────────────────────────────────── */
let t = 0;
function animate() {
    requestAnimationFrame(animate);
    t += CONFIG.animStep;

    // Planeta — rotación lenta
    planetMesh.rotation.y += CONFIG.planetRotSpeed;

    // Energy fields — rotación + flotación suave (Float de drei)
    energyGroupA.rotation.x = Math.PI / 4 + Math.sin(t * CONFIG.floatFreqX) * CONFIG.floatAmpX + t * CONFIG.energyARotX;
    energyGroupA.rotation.y = Math.cos(t * CONFIG.floatFreqY) * CONFIG.floatAmpY + t * CONFIG.energyARotY;

    energyGroupB.rotation.x = Math.PI / 4 - Math.sin(t * CONFIG.floatFreqX * 1.1) * CONFIG.floatAmpX + t * CONFIG.energyBRotX;
    energyGroupB.rotation.y = -Math.cos(t * CONFIG.floatFreqY * 0.9) * CONFIG.floatAmpY + t * CONFIG.energyBRotY;

    // Red de nodos — órbita
    netRoot.rotation.y = t * CONFIG.networkRotY;
    netRoot.rotation.x = Math.sin(t * 0.06) * 0.03;

    // Pulse halos
    for (let i = 0; i < haloMats.length; i++) {
        haloMats[i].opacity = 0.06 + 0.12 * (0.5 + 0.5 * Math.sin(t * haloSpeeds[i] + i * 0.9));
    }

    // Packets
    for (const p of packets) {
        p.t += p.speed * p.dir;
        if (p.t >= 1) { p.t = 1; p.dir = -1; }
        if (p.t <= 0) { p.t = 0; p.dir = 1; }
        p.mesh.position.lerpVectors(p.from, p.to, p.t);
    }

    // Camera parallax
    camera.position.x += (mx * CONFIG.parallaxX - camera.position.x) * CONFIG.parallaxLerp;
    camera.position.y += (-my * CONFIG.parallaxY + CONFIG.cameraY - camera.position.y) * CONFIG.parallaxLerp;
    camera.lookAt(0, 0, 0);

    composer.render();
}

/* ──────────────────────────────────────────────────────────
   Init
   ────────────────────────────────────────────────────────── */
resize();
updatePlanetPosition();
window.addEventListener('resize', () => { resize(); updatePlanetPosition(); });
animate();
