<template>
  <div v-if="groupedButtons.size > 0" class="feature-controls">
    <div v-for="[group, buttons] in groupedButtons" :key="group" class="feature-group">
      <div v-if="group !== 'default'" class="group-title">{{ group }}</div>
      <div class="button-list">
        <button
          v-for="btn in buttons"
          :key="btn.id"
          :class="['feature-btn', { active: getState(btn.id) }]"
          :title="btn.label"
          @click="toggleState(btn.id)"
        >
          <span v-if="btn.icon" class="btn-icon">{{ btn.icon }}</span>
          <span class="btn-label">{{ btn.label }}</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { FeatureButton } from './lib/adapter/IAvatarManifest'

const props = defineProps<{
  featureButtons: FeatureButton[]
  modelValue: Record<string, boolean>
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: Record<string, boolean>): void
}>()

const groupedButtons = computed(() => {
  const groups = new Map<string, FeatureButton[]>()

  props.featureButtons.forEach((btn) => {
    const group = btn.group || 'default'
    if (!groups.has(group)) {
      groups.set(group, [])
    }
    groups.get(group)!.push(btn)
  })

  return groups
})

const getState = (id: string): boolean => {
  return props.modelValue[id] ?? false
}

const toggleState = (id: string) => {
  emit('update:modelValue', {
    ...props.modelValue,
    [id]: !getState(id)
  })
}
</script>

<style scoped>
.feature-controls {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px;
  background: rgba(0, 0, 0, 0.3);
  border-radius: 8px;
  min-width: 120px;
}

.feature-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.group-title {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.6);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 2px;
}

.button-list {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.feature-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border: none;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.1);
  color: rgba(255, 255, 255, 0.7);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.feature-btn:hover {
  background: rgba(255, 255, 255, 0.2);
  color: rgba(255, 255, 255, 0.9);
}

.feature-btn.active {
  background: rgba(100, 180, 255, 0.4);
  color: white;
}

.btn-icon {
  font-size: 14px;
}

.btn-label {
  white-space: nowrap;
}
</style>
