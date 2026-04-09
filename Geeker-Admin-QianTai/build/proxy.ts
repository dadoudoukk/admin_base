import type { ProxyOptions } from "vite";

type ProxyItem = [string, string];

type ProxyList = ProxyItem[];

type ProxyTargetList = Record<string, ProxyOptions>;

/**
 * 创建代理，用于解析 .env.development 代理配置
 * @param list
 */
export function createProxy(list: ProxyList = []) {
  const ret: ProxyTargetList = {};
  for (const [prefix, target] of list) {
    const httpsRE = /^https:\/\//;
    const isHttps = httpsRE.test(target);

    // FastAPI 业务路由挂在 /api 下，代理须把 /api/... 原样转发到后端，不能剥掉前缀，
    // 否则会变成 http://127.0.0.1:8000/login 导致 404（正确应为 .../api/login）。
    // https://github.com/http-party/node-http-proxy#options
    ret[prefix] = {
      target: target,
      changeOrigin: true,
      ws: true,
      // https is require secure=false
      ...(isHttps ? { secure: false } : {})
    };
  }
  return ret;
}
