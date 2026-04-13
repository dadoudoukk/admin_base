<template>
  <div class="card content-box link-iframe-shell">
    <iframe :src="iframeSrc" class="full-iframe" title="嵌入页"></iframe>
  </div>
</template>

<script setup lang="ts" name="LinkIframe">
import { computed } from "vue";
import { useRoute } from "vue-router";

const route = useRoute();

/** 与 axios 的 VITE_API_URL 一致：完整 URL 则拼接 /docs；开发环境为 /api 时走同源 /docs（由 Vite 代理到后端）。 */
function swaggerDocsUrl(): string {
  const api = String(import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");
  if (/^https?:\/\//i.test(api)) return `${api}/docs`;
  if (typeof window === "undefined") return "/docs";
  return `${window.location.origin}/docs`;
}

const iframeSrc = computed(() => {
  if (route.name === "apiDocs") return swaggerDocsUrl();
  return "https://cn.bing.com/";
});
</script>

<style scoped lang="scss">
@import "./index.scss";
</style>
