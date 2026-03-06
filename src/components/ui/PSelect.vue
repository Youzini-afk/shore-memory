<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import PixelIcon from './PixelIcon.vue'

interface Option {
  label: string
  value: string | number
  disabled?: boolean
  icon?: string
}

const props = defineProps<{
  modelValue: string | number
  options: Option[]
  label?: string
  icon?: string
  placeholder?: string
  disabled?: boolean
  size?: 'sm' | 'md' | 'lg'
  clearable?: boolean
  variant?: 'default' | 'white'
}>()

const emit = defineEmits(['update:modelValue', 'change'])

const isOpen = ref(false)
const containerRef = ref<HTMLElement | null>(null)

const selectedOption = computed(() => {
  return props.options.find((opt) => opt.value === props.modelValue)
})

const toggleDropdown = () => {
  if (props.disabled) return
  isOpen.value = !isOpen.value
}

const selectOption = (option: Option) => {
  if (option.disabled) return
  emit('update:modelValue', option.value)
  emit('change', option.value)
  isOpen.value = false
}

const handleClickOutside = (event: MouseEvent) => {
  if (containerRef.value && !containerRef.value.contains(event.target as Node)) {
    isOpen.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>

<template>
  <div ref="containerRef" class="space-y-2 w-full">
    <!-- 标签 🐾 -->
    <label
      v-if="label"
      class="text-[10px] font-black text-slate-400 uppercase tracking-widest flex items-center gap-2 px-1"
    >
      <PixelIcon v-if="icon" :name="icon" size="xs" class="opacity-70" />
      {{ label }}
    </label>

    <div class="relative inline-block w-full">
      <button
        type="button"
        class="w-full flex items-center justify-between border transition-all focus:outline-none group/sel rounded-2xl"
        :class="[
          variant === 'white'
            ? 'bg-white border-slate-100 focus:border-sky-300 focus:ring-4 focus:ring-sky-50'
            : 'bg-white/50 border-sky-100 focus:border-sky-300 focus:ring-4 focus:ring-sky-100',
          disabled
            ? 'opacity-50 cursor-not-allowed'
            : 'hover:bg-white/80 cursor-pointer hover:border-sky-200',
          size === 'sm' ? 'px-2 py-1 text-xs' : 'px-4 py-2.5 text-sm',
          isOpen ? 'border-sky-300 ring-4 ring-sky-100 shadow-xl shadow-sky-200/20' : ''
        ]"
        @click="toggleDropdown"
      >
        <span
          :class="selectedOption ? 'text-slate-700 font-medium' : 'text-slate-400'"
          class="flex items-center gap-1.5"
        >
          <span
            v-if="selectedOption"
            class="opacity-0 group-hover/sel:opacity-100 transition-opacity text-[10px] text-sky-400"
          >
            <PixelIcon name="paw" size="xs" />
          </span>
          <PixelIcon
            v-if="selectedOption?.icon"
            :name="selectedOption.icon"
            size="xs"
            class="opacity-70"
          />
          {{ selectedOption?.label || placeholder || 'Select...' }}
        </span>
        <PixelIcon
          name="chevron-down"
          size="xs"
          class="text-slate-400 transition-transform duration-300"
          :class="{ 'rotate-180 text-sky-400': isOpen }"
        />
      </button>

      <Transition
        enter-active-class="transition duration-100 ease-out"
        enter-from-class="transform scale-95 opacity-0"
        enter-to-class="transform scale-100 opacity-100"
        leave-active-class="transition duration-75 ease-in"
        leave-from-class="transform scale-100 opacity-100"
        leave-to-class="transform scale-95 opacity-0"
      >
        <div
          v-if="isOpen"
          class="absolute z-50 w-full mt-2 bg-white/95 backdrop-blur-xl border border-sky-100 rounded-2xl shadow-2xl shadow-sky-200/30 py-1.5 overflow-hidden ring-1 ring-black/5"
        >
          <div class="max-h-60 overflow-y-auto custom-scrollbar">
            <div
              v-for="option in options"
              :key="option.value"
              class="px-4 py-2.5 text-sm cursor-pointer transition-all flex items-center justify-between group/opt"
              :class="[
                modelValue === option.value
                  ? 'bg-sky-50 text-sky-600 font-bold'
                  : 'text-slate-600 hover:bg-slate-50 hover:text-sky-500',
                option.disabled ? 'opacity-50 cursor-not-allowed grayscale' : ''
              ]"
              @click="selectOption(option)"
            >
              <div class="flex items-center gap-2.5">
                <PixelIcon v-if="option.icon" :name="option.icon" size="xs" class="opacity-70" />
                {{ option.label }}
              </div>
              <PixelIcon
                v-if="modelValue === option.value"
                name="check"
                size="xs"
                class="text-sky-500 animate-in zoom-in-50 duration-300"
              />
            </div>
          </div>
        </div>
      </Transition>
    </div>
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.05);
  border-radius: 2px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.1);
}
</style>
