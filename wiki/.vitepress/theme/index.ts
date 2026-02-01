import DefaultTheme from 'vitepress/theme'
import type { Theme } from 'vitepress'
import { inBrowser } from 'vitepress'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import ArchitectureGraph from '../components/ArchitectureGraph.vue'
import MemoryNetworkGraph from '../components/MemoryNetworkGraph.vue'
import BedrockDemo from '../components/BedrockDemo.vue'
import MDPGraph from '../components/MDPGraph.vue'
import DashboardDemo from '../components/DashboardDemo.vue'
import './style.css'

export default {
  extends: DefaultTheme,
  enhanceApp({ app, router }) {
    app.use(ElementPlus)
    app.component('ArchitectureGraph', ArchitectureGraph)
    app.component('MemoryNetworkGraph', MemoryNetworkGraph)
    app.component('BedrockDemo', BedrockDemo)
    app.component('MDPGraph', MDPGraph)
    app.component('DashboardDemo', DashboardDemo)
    
    if (inBrowser) {
      // @ts-ignore
      if (!document.startViewTransition) return

      router.onBeforeRouteChange = (to) => {
        // @ts-ignore
        const transition = document.startViewTransition(() => {
          // The promise is resolved when the DOM is updated
        })
        
        transition.finished.then(() => {
          // Cleanup if needed
        })
      }
    }
  }
} satisfies Theme
