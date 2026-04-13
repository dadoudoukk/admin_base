import { defineStore } from "pinia";
import { GlobalState } from "@/stores/interface";
import { DEFAULT_PRIMARY } from "@/config";
import piniaPersistConfig from "@/stores/helper/persist";
import { getSysConfigAll } from "@/api/modules/sysConfig";

const DEFAULT_APP_LOGO = new URL("../../assets/images/logo.svg", import.meta.url).href;

export const useGlobalStore = defineStore({
  id: "geeker-global",
  // 修改默认值之后，需清除 localStorage 数据
  state: (): GlobalState => ({
    // 布局模式 (纵向：vertical | 经典：classic | 横向：transverse | 分栏：columns)
    layout: "vertical",
    // element 组件大小
    assemblySize: "default",
    // 当前系统语言
    language: null,
    // 当前页面是否全屏
    maximize: false,
    // 主题颜色
    primary: DEFAULT_PRIMARY,
    // 深色模式
    isDark: false,
    // 灰色模式
    isGrey: false,
    // 色弱模式
    isWeak: false,
    // 侧边栏反转
    asideInverted: false,
    // 头部反转
    headerInverted: false,
    // 折叠菜单
    isCollapse: false,
    // 菜单手风琴
    accordion: true,
    // 页面水印
    watermark: false,
    // 面包屑导航
    breadcrumb: true,
    // 面包屑导航图标
    breadcrumbIcon: true,
    // 标签页
    tabs: true,
    // 标签页图标
    tabsIcon: true,
    // 页脚
    footer: true,
    sysConfigMap: {} as Record<string, unknown>
  }),
  getters: {
    /** 优先 sysConfigMap.sys_app_name，否则环境变量标题 */
    displayAppTitle(): string {
      const raw = this.sysConfigMap["sys_app_name"];
      if (raw != null && String(raw).trim() !== "") return String(raw).trim();
      return import.meta.env.VITE_GLOB_APP_TITLE;
    },
    /** 优先 sysConfigMap.sys_logo（URL），否则默认本地 Logo */
    displayAppLogo(): string {
      const raw = this.sysConfigMap["sys_logo"];
      if (raw != null && String(raw).trim() !== "") return String(raw).trim();
      return DEFAULT_APP_LOGO;
    }
  },
  actions: {
    // Set GlobalState
    setGlobalState(...args: ObjToKeyValArray<GlobalState>) {
      this.$patch({ [args[0]]: args[1] });
    },
    async initSysConfig() {
      try {
        const res = await getSysConfigAll();
        const map = res.data?.map;
        this.sysConfigMap = map && typeof map === "object" && !Array.isArray(map) ? { ...map } : {};
      } catch {
        this.sysConfigMap = {};
      }
    }
  },
  persist: piniaPersistConfig("geeker-global")
});
