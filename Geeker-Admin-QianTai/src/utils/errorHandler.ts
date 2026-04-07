import { ElNotification } from "element-plus";
import { isAxiosError } from "axios";

/** axios 拦截器里 Promise.reject 的业务体：{ code, msg, data }，不能再交给 Notification 当 message（会变成整段 JSON） */
function isRejectedBusinessPayload(err: unknown): err is { code: number; msg?: unknown; data?: unknown; message?: unknown } {
  if (err === null || typeof err !== "object" || Array.isArray(err)) return false;
  const o = err as Record<string, unknown>;
  return typeof o.code === "number";
}

function pickPlainText(err: unknown): string {
  if (typeof err === "string") return err.trim();
  if (err instanceof Error) return (err.message || "").trim();
  if (err && typeof err === "object" && !Array.isArray(err)) {
    const o = err as Record<string, unknown>;
    for (const key of ["msg", "message", "detail"] as const) {
      const v = o[key];
      if (typeof v === "string" && v.trim()) return v.trim();
    }
  }
  return "";
}

/**
 * @description 全局代码错误捕捉（勿把对象直接塞给 ElNotification.message）
 */
const errorHandler = (error: unknown) => {
  if (
    error &&
    typeof error === "object" &&
    "status" in error &&
    ((error as { status?: unknown }).status || (error as { status?: unknown }).status === 0)
  ) {
    return false;
  }
  if (isAxiosError(error)) {
    return false;
  }
  // 业务码错误已在 src/api/index.ts 里 ElMessage 提示过，避免二次弹 Notification 且整段 JSON
  if (isRejectedBusinessPayload(error) && error.code !== 200) {
    return false;
  }

  const errorMap: Record<string, string> = {
    InternalError: "Javascript引擎内部错误",
    ReferenceError: "未找到对象",
    TypeError: "使用了错误的类型或对象",
    RangeError: "使用内置对象时，参数超范围",
    SyntaxError: "语法错误",
    EvalError: "错误的使用了Eval",
    URIError: "URI错误"
  };

  const name = error instanceof Error ? error.name : "";
  const errorName = errorMap[name] || "未知错误";
  const messageText = pickPlainText(error) || "请稍后重试或联系管理员";

  ElNotification({
    title: errorName,
    message: messageText,
    type: "error",
    duration: 3000
  });
};

export default errorHandler;
