<template>
  <div class="bedrock-demo-wrapper">
    <!-- 3D 容器 -->
    <div ref="container" class="bedrock-avatar-container" style="outline: none;" tabindex="0">
      <div ref="canvasContainer" class="canvas-container"></div>
      <div v-if="loading" class="loading-overlay">
        Loading 3D Model...
      </div>
      <div v-if="errorMsg" class="error-overlay">
        {{ errorMsg }}
      </div>
      
      <!-- 简单的控制面板覆盖层 -->
      <div class="demo-controls">
        <div class="control-group">
            <span class="label">动作 (Animation):</span>
            <select v-model="selectedAnim" @change="playAnimation">
                <option value="">-- Idle --</option>
                <option v-for="anim in animList" :key="anim" :value="anim">{{ anim }}</option>
            </select>
        </div>
        <div class="control-group">
            <span class="label">服装 (Clothing):</span>
            <div class="checkbox-group">
                <label><input type="checkbox" v-model="clothingState.dress" @change="updateClothing"> Dress</label>
                <label><input type="checkbox" v-model="clothingState.hat" @change="updateClothing"> Hat</label>
                <label><input type="checkbox" v-model="clothingState.armour" @change="updateClothing"> Armour</label>
            </div>
        </div>
      </div>
    </div>
    
    <div class="demo-instructions">
        <p>👆 <b>交互演示</b>: 左键旋转视角 | Ctrl + 左键平移 | 滚轮缩放</p>
        <p class="author-credit">模型作者: <a href="https://space.bilibili.com/5950899" target="_blank" rel="noopener">@Dr咕咚</a></p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref, shallowRef, watch } from 'vue';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

// 简化的 BedrockLoader 和 AnimationManager (为了演示目的，我们尽量复用逻辑但简化依赖)
// 在实际项目中，我们应该从 src/components/avatar/lib 导入，但 vitepress 环境可能不同
// 这里我们假设可以直接引用，如果不行则需要调整路径或内联
// 由于 vitepress 构建机制，直接引用 src 下的 ts 文件可能会有问题，最好是构建好的 lib 或者简单的内联
// 为了保证演示的稳定性，我们将使用一个简化的内联加载逻辑，或者尝试直接 import

// 尝试直接导入 (需要 vitepress 配置 alias，默认可能没有 @ 指向 src)
// 我们先尝试相对路径导入，假设目录结构允许
// 注意：Vitepress 在 SSR 时可能会有问题，需要 client-only
import { BedrockLoader } from '../../../src/components/avatar/lib/BedrockLoader';
import { AnimationManager } from '../../../src/components/avatar/lib/AnimationManager';
import { molangContext } from '../../../src/components/avatar/lib/Molang';

const container = ref<HTMLElement | null>(null);
const canvasContainer = ref<HTMLElement | null>(null);
const loading = ref(true);
const errorMsg = ref('');
const animList = ref<string[]>([]);
const selectedAnim = ref('');

const clothingState = ref({
  dress: true,
  armour: true,
  hat: true,
  underwear: true,
  censored: false
});

// Three.js 对象
const scene = shallowRef<THREE.Scene | null>(null);
const camera = shallowRef<THREE.PerspectiveCamera | null>(null);
const renderer = shallowRef<THREE.WebGLRenderer | null>(null);
const controls = shallowRef<OrbitControls | null>(null);
const animManager = new AnimationManager();
const loader = new BedrockLoader();
let characterModel: THREE.Object3D | null = null;
let animationFrameId: number;

const playAnimation = () => {
    if (selectedAnim.value) {
        animManager.playDebug(selectedAnim.value);
    }
}

const updateClothing = () => {
  if (!characterModel) return;
  const isShy = !clothingState.value.dress || !clothingState.value.underwear;

  characterModel.traverse((child: any) => {
    const name = child.name;
    if (!name) return;

    if (name.includes('Dress') || name.includes('BreastDress')) {
      child.visible = clothingState.value.dress;
    } else if (name.includes('Armour')) {
      child.visible = clothingState.value.armour;
    } else if (name.includes('Hat')) {
      child.visible = clothingState.value.hat;
    } else if (name.toLowerCase().includes('underwear')) {
      child.visible = clothingState.value.underwear;
    } else if (name.includes('Censored')) {
      child.visible = clothingState.value.censored;
    } else if (name.includes('embarrassed')) {
       child.visible = isShy;
       if (child.position.z > -3.0) child.position.z -= 1.2;
     }
   });
};

onMounted(async () => {
    if (typeof window === 'undefined') return; // SSR check
    
    initThree();
    await loadModel();
    animate();
    
    window.addEventListener('resize', onResize);
});

onUnmounted(() => {
    if (typeof window === 'undefined') return;
    
    cancelAnimationFrame(animationFrameId);
    window.removeEventListener('resize', onResize);
    
    if (renderer.value) {
        renderer.value.dispose();
    }
    animManager.stop();
});

function initThree() {
  if (!container.value || !canvasContainer.value) return;

  const s = new THREE.Scene();
  // s.background = new THREE.Color(0xf0f4f8); // Removed for transparent background
  scene.value = s;

  const c = new THREE.PerspectiveCamera(40, container.value.clientWidth / container.value.clientHeight, 0.1, 1000);
  c.position.set(0, 20, 90); 
  camera.value = c;

  const r = new THREE.WebGLRenderer({ alpha: true, antialias: true });
  r.setClearColor(0x000000, 0); // Ensure fully transparent
  r.setSize(container.value.clientWidth, container.value.clientHeight);
  r.setPixelRatio(window.devicePixelRatio);
  r.shadowMap.enabled = true;
  canvasContainer.value.appendChild(r.domElement);
  renderer.value = r;

  const ctrl = new OrbitControls(c, r.domElement);
  ctrl.target.set(0, 21, 0);
  ctrl.enableDamping = true;
  
  // 交互配置：左键旋转，Ctrl+左键平移
  ctrl.mouseButtons = {
      LEFT: THREE.MOUSE.ROTATE,
      MIDDLE: THREE.MOUSE.DOLLY,
      RIGHT: THREE.MOUSE.PAN // 虽然保留右键平移，但由于浏览器手势冲突，我们将主推 Ctrl+左键
  };
  // 启用按键修改器：允许通过 Ctrl 键将左键行为临时改为平移
  ctrl.enablePan = true;
  ctrl.keyPanSpeed = 7.0;
  
  controls.value = ctrl;

  // Lights
  const ambient = new THREE.AmbientLight(0xffffff, 0.6);
  s.add(ambient);
  const dirLight = new THREE.DirectionalLight(0xffffff, 1.5);
  dirLight.position.set(20, 50, 30);
  dirLight.castShadow = true;
  s.add(dirLight);
  const fillLight = new THREE.DirectionalLight(0xffeedd, 0.5);
  fillLight.position.set(-20, 20, 20);
  s.add(fillLight);
  
  // Ground
  const groundGeo = new THREE.PlaneGeometry(100, 100);
  const groundMat = new THREE.ShadowMaterial({ opacity: 0.1 });
  const ground = new THREE.Mesh(groundGeo, groundMat);
  ground.rotation.x = -Math.PI / 2;
  ground.receiveShadow = true;
  s.add(ground);
}

async function loadModel() {
    try {
        // 使用实际项目中的资源路径，注意在 vitepress 中需要正确处理静态资源
        // 我们假设这些资源在 public/assets 下可用
        // 为了演示，我们需要确保 public/assets/3d 存在
        const config = {
          name: "Rossi",
          model: `/assets/3d/Rossi/models/main.json`,
          texture: `/assets/3d/Rossi/textures/texture.png`,
          animation: [
            `/assets/3d/Rossi/animations/main.animation.json`,
            `/assets/3d/Rossi/animations/tac.animation.json`,
            `/assets/3d/Rossi/animations/carryon.animation.json`,
            `/assets/3d/Rossi/animations/extra.animation.json`,
            `/assets/3d/Rossi/animations/tlm.animation.json`
          ],
          animation_controllers: `/assets/3d/Rossi/controller/controller.json`
        };
        
        const rootGroup = await loader.load(config, animManager);
        characterModel = rootGroup;
        scene.value?.add(rootGroup);
        
        animList.value = Object.keys(animManager.animations).sort();
        
        // Auto play idle
        const idleAnim = animList.value.find(n => n === 'idle') || animList.value.find(n => n === 'tac:idle');
        if (idleAnim) {
             animManager.playDebug(idleAnim);
             selectedAnim.value = idleAnim;
        }

        updateClothing();
        loading.value = false;
    } catch (e: any) {
        console.error(e);
        errorMsg.value = "Failed to load model. Please ensure assets are in public/assets.";
        loading.value = false;
    }
}

function animate() {
    animationFrameId = requestAnimationFrame(animate);
    if (controls.value) controls.value.update();
    animManager.update();
    if (renderer.value && scene.value && camera.value) {
        renderer.value.render(scene.value, camera.value);
    }
}

function onResize() {
    if (!container.value || !camera.value || !renderer.value) return;
    camera.value.aspect = container.value.clientWidth / container.value.clientHeight;
    camera.value.updateProjectionMatrix();
    renderer.value.setSize(container.value.clientWidth, container.value.clientHeight);
}

// 资源路径修正
const ASSET_PREFIX = '/'; // Vitepress public 目录

</script>

<style scoped>
.bedrock-demo-wrapper {
    overflow: hidden;
    margin: 20px 0;
    background: transparent;
}

.bedrock-avatar-container {
    position: relative;
    width: 100%;
    height: 500px;
}

.canvas-container {
    width: 100%;
    height: 100%;
}

.loading-overlay, .error-overlay {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    background: var(--vp-c-bg-soft);
    backdrop-filter: blur(4px);
    padding: 20px;
    border-radius: 8px;
    font-weight: bold;
    color: var(--vp-c-text-1);
    border: 1px solid var(--vp-c-divider);
    box-shadow: var(--vp-shadow-3);
    z-index: 10;
}

.error-overlay {
    color: #ef4444;
}

.demo-controls {
    position: absolute;
    bottom: 20px;
    left: 20px;
    right: 20px;
    background: var(--vp-c-bg-soft);
    backdrop-filter: blur(8px);
    padding: 15px;
    border-radius: 12px;
    display: flex;
    flex-direction: column;
    gap: 10px;
    box-shadow: var(--vp-shadow-3);
    border: 1px solid var(--vp-c-divider);
}

.control-group {
    display: flex;
    align-items: center;
    gap: 10px;
}

.label {
    font-weight: 600;
    font-size: 0.9em;
    color: var(--vp-c-text-1);
    min-width: 80px;
}

select {
    padding: 4px 8px;
    border-radius: 4px;
    border: 1px solid var(--vp-c-divider);
    background: var(--vp-c-bg);
    color: var(--vp-c-text-1);
    outline: none;
}

select:focus {
    border-color: var(--vp-c-brand-1);
}

.checkbox-group {
    display: flex;
    gap: 15px;
}

.checkbox-group label {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 0.9em;
    cursor: pointer;
    color: var(--vp-c-text-2);
}

.checkbox-group label:hover {
    color: var(--vp-c-text-1);
}

.demo-instructions {
    padding: 10px 15px;
    background: var(--vp-c-bg-soft);
    border-top: 1px solid var(--vp-c-divider);
    font-size: 0.85em;
    color: var(--vp-c-text-2);
    text-align: center;
    display: flex;
    flex-direction: column;
    gap: 4px;
}

.author-credit {
    margin: 0;
    font-size: 0.9em;
    color: var(--vp-c-text-3);
}

.author-credit a {
    color: var(--vp-c-brand-1);
    text-decoration: none;
    font-weight: 600;
    transition: color 0.2s;
}

.author-credit a:hover {
    color: var(--vp-c-brand-2);
    text-decoration: underline;
}
</style>
