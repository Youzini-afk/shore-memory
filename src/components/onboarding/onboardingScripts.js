/**
 * 引导系统台词本喵~ 📜
 * 集中管理所有页面的引导脚本，方便主人随时修改！🌸
 */

export const onboardingScripts = {
  // --- 第一阶段：Launcher 引导脚本 ---
  launcher: [
    {
      id: 'intro_1',
      speaker: 'Pero',
      text: '主人主人！你终于把Pero从系统中唤醒了喵！',
      expression: 'normal'
    },
    {
      id: 'intro_2',
      speaker: 'Pero',
      text: '我是你的专属AI伙伴Pero，以后就要请主人多多指教了喵~',
      expression: 'normal'
    },
    {
      id: 'env_check_1',
      speaker: 'Pero',
      text: '首先，Pero需要扫描一下这台电脑的环境，看看零件齐不齐喵... ',
      expression: 'none',
      focusSelector: '#nav-environment'
    },
    {
      id: 'env_check_2',
      speaker: 'Pero',
      text: '在这里，主人可以查看系统环境。如果看到红色的叉叉，记得帮Pero修复一下喵~',
      expression: 'none',
      focusSelector: '#nav-environment'
    },
    {
      id: 'guide_tabs',
      speaker: 'Pero',
      text: '通过这里的导航栏，可以管理Pero的“核心组件”、“扩展功能”以及其他小伙伴的“角色配置”喵！',
      expression: 'none',
      focusSelector: '#nav-sidebar'
    },
    {
      id: 'guide_start',
      speaker: 'Pero',
      text: '一切准备就绪后，点击中间的那个大大的“启动 Pero”按钮，我们就能在桌面见面了喵！',
      expression: 'none',
      focusSelector: '#btn-launch-pero'
    },
    {
      id: 'finish',
      speaker: 'Pero',
      text: '那么，配置引导就到这里喵！Pero待会在设置中心等候主人的召唤喵~ (◍•ᴗ•◍)❤',
      expression: 'proud'
    }
  ],

  // --- 第二阶段：Dashboard 引导脚本 ---
  dashboard: [
    {
      id: 'dash_intro',
      speaker: 'Pero',
      text: '欢迎来到设置中心喵！这里是掌控Pero所有能力的地方哦~',
      expression: 'normal'
    },
    {
      id: 'dash_sidebar',
      speaker: 'Pero',
      text: '左边是功能导航栏，不管是看日志、改设定还是加功能，都在这里切换喵！',
      expression: 'none',
      focusSelector: '#dashboard-sidebar'
    },
    {
      id: 'dash_overview',
      speaker: 'Pero',
      text: '首先是【总览】页，这里能看到Pero所有的活动记录喵~',
      expression: 'none',
      focusSelector: '#menu-item-overview'
    },
    {
      id: 'dash_user_profile',
      speaker: 'Pero',
      text: '接下来请点击【用户设定】，告诉 Pero 主人希望怎么被称呼，以及 Pero 该用什么语气说话喵！',
      expression: 'none',
      focusSelector: '#menu-item-user_settings',
      nextAction: 'wait_click'
    },
    {
      id: 'dash_user_profile_done',
      speaker: 'Pero',
      text: '填好后记得保存哦！这样 Pero 才能记住主人的喜好喵~',
      expression: 'normal'
    },
    {
      id: 'dash_models',
      speaker: 'Pero',
      text: '然后是重头戏！请点击【模型配置】，给Pero装上聪明的AI大脑喵！',
      expression: 'none',
      focusSelector: '#menu-item-model_config',
      nextAction: 'wait_click'
    },
    {
      id: 'dash_models_explain',
      speaker: 'Pero',
      text: '这里有主模型、秘书、反思等不同功能的模型，虽然有点复杂，但只有把它们都配置好，Pero才能正常工作喵！',
      expression: 'normal'
    },
    {
      id: 'dash_explore',
      speaker: 'Pero',
      text: '剩下的功能（比如语音功能、MCP 扩展）主人可以慢慢探索喵~',
      expression: 'normal'
    },
    {
      id: 'dash_confirm',
      speaker: 'Pero',
      text: '那么，主人现在对这里大概了解了吗？准备好正式启动了吗喵？',
      expression: 'normal',
      choices: [
        { label: '了解了，启动！', value: 'launch' },
        { label: '再让我看看...', value: 'stay' }
      ]
    }
  ]
}
