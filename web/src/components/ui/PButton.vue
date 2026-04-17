<script setup lang="ts">
interface Props {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  size?: 'sm' | 'md'
  block?: boolean
  loading?: boolean
  as?: 'button' | 'a'
  type?: 'button' | 'submit' | 'reset'
}
const props = withDefaults(defineProps<Props>(), {
  variant: 'secondary',
  size: 'md',
  as: 'button',
  type: 'button'
})

const sizeCls =
  props.size === 'sm'
    ? 'h-8 px-3 text-[12px] gap-1.5'
    : 'h-9 px-4 text-[13px] gap-2'

const variantCls = (() => {
  switch (props.variant) {
    case 'primary':
      return 'bg-gradient-to-b from-accent-hi to-accent-lo text-white shadow-accent hover:shadow-accent-lg hover:-translate-y-[1px]'
    case 'danger':
      return 'bg-transparent border border-state-invalidated/30 text-state-invalidated hover:bg-state-invalidated/10'
    case 'ghost':
      return 'text-ink-3 hover:text-ink-1 hover:bg-shore-hover'
    case 'secondary':
    default:
      return 'bg-shore-card border border-shore-line text-ink-1 hover:bg-shore-elev hover:border-shore-border'
  }
})()
</script>

<template>
  <component
    :is="as"
    :type="as === 'button' ? type : undefined"
    class="inline-flex items-center justify-center rounded-btn font-display font-medium transition duration-240 ease-shore select-none disabled:opacity-50 disabled:cursor-not-allowed"
    :class="[sizeCls, variantCls, block ? 'w-full' : '']"
  >
    <span v-if="loading" class="inline-block h-3 w-3 rounded-full border border-current border-t-transparent animate-spin" />
    <slot />
  </component>
</template>
