<template>
  <div class="login-container-wrapper" @mousemove="handleMouseMove">
    <div class="illustration-side">
      <div class="character-group" :class="{ 'eyes-closed': isEyesClosedAndLeaningLeft }" :style="groupStyle">
        <div class="character char-purple-skew" :style="getCharStyle(0)">
          <div class="static-features">
            <div class="eye">
              <div class="pupil" :style="getPupilStyle()"></div>
            </div>
            <div class="eye">
              <div class="pupil" :style="getPupilStyle()"></div>
            </div>
          </div>
        </div>

        <div class="character char-black-rect" :style="getCharStyle(1)">
          <div class="static-features">
            <div class="eye">
              <div class="pupil" :style="getPupilStyle()"></div>
            </div>
            <div class="eye">
              <div class="pupil" :style="getPupilStyle()"></div>
            </div>
          </div>
        </div>

        <div class="character char-orange-arch" :style="getCharStyle(2)">
          <div class="static-features">
            <div class="eye">
              <div class="pupil" :style="getPupilStyle()"></div>
            </div>
            <div class="eye">
              <div class="pupil" :style="getPupilStyle()"></div>
            </div>
          </div>
        </div>

        <div class="character char-yellow-arch" :style="getCharStyle(3)">
          <div class="interactive-features">
            <div class="eyes-container">
              <div class="eye">
                <div class="pupil" :style="getPupilStyle()"></div>
              </div>
              <div class="eye">
                <div class="pupil" :style="getPupilStyle()"></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="form-side">
      <div class="login-container">
        <h1>欢迎回来！</h1>
        <p class="subtitle">请输入您的详细信息</p>

        <form @submit.prevent="handleLogin">
          <div class="form-group">
            <label for="email">账号</label>
            <input
              id="email"
              v-model="loginForm.username"
              type="text"
              placeholder="请输入您的账号"
              autocomplete="username"
              @focus="isPeeking = true"
              @blur="isPeeking = false"
            />
          </div>

          <div class="form-group">
            <label for="password">密码</label>
            <div style="position: relative">
              <input
                id="password"
                v-model="loginForm.password"
                :type="passwordType"
                placeholder="请输入密码"
                autocomplete="current-password"
                @focus="isPeeking = true"
                @blur="isPeeking = false"
              />
              <span class="password-toggle" @click="togglePassword">
                <svg
                  v-if="!isEyesClosedAndLeaningLeft"
                  class="eye-open"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                  <circle cx="12" cy="12" r="3"></circle>
                </svg>
                <svg
                  v-else
                  class="eye-closed"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <path
                    d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"
                  ></path>
                  <line x1="1" y1="1" x2="23" y2="23"></line>
                </svg>
              </span>
            </div>
          </div>

          <button type="submit" class="btn-primary">登录</button>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import { HOME_URL } from "@/config";
import { loginApi } from "@/api/modules/login";
import { useUserStore } from "@/stores/modules/user";
import { useTabsStore } from "@/stores/modules/tabs";
import { useKeepAliveStore } from "@/stores/modules/keepAlive";
import { initDynamicRouter } from "@/routers/modules/dynamicRouter";
// === 1. 状态定义 ===
const isEyesClosedAndLeaningLeft = ref(false);
const isPeeking = ref(false);
const mouseX = ref(0);
const mouseY = ref(0);

// 表单数据绑定
const loginForm = reactive({
  username: "",
  password: ""
});

// router + pinia store 实例（给 handleLogin 使用）
const router = useRouter();
const userStore = useUserStore();
const tabsStore = useTabsStore();
const keepAliveStore = useKeepAliveStore();

// 获取窗口中心点用于计算
let windowCenterX = 0;
let windowCenterY = 0;

onMounted(() => {
  windowCenterX = window.innerWidth / 2;
  windowCenterY = window.innerHeight / 2;
  mouseX.value = windowCenterX;
  mouseY.value = windowCenterY;
});

// === 2. 交互逻辑 ===

// 监听鼠标移动
const handleMouseMove = (e: MouseEvent) => {
  mouseX.value = e.clientX;
  mouseY.value = e.clientY;
};

// 切换密码可见性
const togglePassword = () => {
  isEyesClosedAndLeaningLeft.value = !isEyesClosedAndLeaningLeft.value;
};

// 计算密码框类型
const passwordType = computed(() => {
  return isEyesClosedAndLeaningLeft.value ? "text" : "password";
});

// === 3. 动画计算逻辑 ===

// 计算整个底座的微风摇摆
const groupStyle = computed(() => {
  if (isEyesClosedAndLeaningLeft.value) return { transform: "none" };

  // 简化的摇摆逻辑
  let groupSkew = ((mouseX.value - windowCenterX) / window.innerWidth) * -8;
  groupSkew = Math.min(Math.max(groupSkew, -6), 6);

  return { transform: `skewX(${groupSkew}deg)` };
});

// 计算每个小人的拉伸与位移 (完美复刻你的身高系数算法)
const getCharStyle = (index: number) => {
  const ratios = [1.8, 3.2, 2.8, 1.5]; // 紫, 黑, 橙, 黄的身高系数
  const heightRatio = ratios[index];

  let translateX = 0;
  let scaleY = 1;
  let skewX = 0;

  if (isEyesClosedAndLeaningLeft.value) {
    translateX = -(index * 22);
    skewX = 10;
    scaleY = 0.95;
  } else if (isPeeking.value) {
    translateX = (3 - index) * 16;
    skewX = -3 * heightRatio;
    scaleY = 1 + 0.05 * heightRatio;
  }

  return {
    transform: `translateX(${translateX}px) skewX(${skewX}deg) scaleY(${scaleY})`
  };
};

// 计算眼珠的跟随移动
const getPupilStyle = () => {
  if (isEyesClosedAndLeaningLeft.value) return {};

  const angle = Math.atan2(mouseY.value - windowCenterY, mouseX.value - windowCenterX);
  const distance = 6; // 眼球移动半径
  const moveX = Math.cos(angle) * distance;
  const moveY = Math.sin(angle) * distance;

  return {
    transform: `translate(calc(-50% + ${moveX}px), calc(-50% + ${moveY}px))`
  };
};

// === 4. 提交表单 ===
const handleLogin = async () => {
  const username = loginForm.username.trim();
  const password = loginForm.password;

  const { data } = await loginApi({ username, password });

  //  写入 Pinia/localStorage（前端 axios 拦截器会从这里取 token，自动加到 x-access-token）
  userStore.setToken(data.access_token);

  //  拉取动态菜单并添加动态路由
  await initDynamicRouter();

  //  清空 tabs/keepAlive，并跳转首页
  await tabsStore.setTabs([]);
  await keepAliveStore.setKeepAliveName([]);
  router.push(HOME_URL);
};
</script>

<style scoped>
/* 使用 scoped 保证这里的样式不会污染后台的其他页面 */
.login-container-wrapper {
  --char-orange: #f06e32;
  --char-black: #000000;
  --char-purple: #4b39f0;
  --char-yellow: #fad02e;
  --text-yellow: #fad02e;
  --bg-dark-start: #353540;
  --bg-dark-end: #2a2a33;
  --primary-purple: #4b39f0;
  --form-bg: #ffffff;
  --form-text: #1a1a1a;
  --form-subtitle: #666666;
  --input-border: #d9d9d9;
  --btn-text: #ffffff;

  display: flex;
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  background-color: var(--form-bg);
}

* {
  box-sizing: border-box;
  padding: 0;
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}

/* === 分屏布局设置 === */
.illustration-side {
  position: relative;
  display: flex;
  flex: 1.2;
  flex-direction: column;
  align-items: center;
  justify-content: flex-end;
  padding-bottom: 120px;
  background: radial-gradient(circle at center, var(--bg-dark-start) 0%, var(--bg-dark-end) 100%);
}

.form-side {
  display: flex;
  flex: 1;
  align-items: center;
  justify-content: center;
  padding: 8% 10%;
  background-color: var(--form-bg);
}

/* === 左侧小人组合容器样式 === */
.character-group {
  position: relative;
  display: flex;
  align-items: flex-end;
  transform-origin: bottom center;
  transition: transform 0.2s ease-out;
}

/* === 通用单独小人样式 === */
.character {
  position: relative;
  display: flex;
  justify-content: center;
  box-shadow: -5px 0 15px rgba(0, 0, 0, 0.15);
  transform-origin: bottom center;
  transition: transform 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.character:not(:first-child) {
  margin-left: -80px;
}

/* === 具体小人定制 === */
.char-purple-skew {
  z-index: 2;
  width: 180px;
  height: 180px;
  background-color: var(--char-purple);
  border-radius: 50% 50% 0 0;
}

.char-black-rect {
  z-index: 1;
  width: 200px;
  height: 320px;
  background-color: var(--char-black);
  border-radius: 50% 50% 0 0;
}

.char-orange-arch {
  z-index: 3;
  width: 180px;
  height: 280px;
  background-color: var(--char-orange);
  border-radius: 50% 50% 0 0;
}

.char-yellow-arch {
  z-index: 4;
  width: 140px;
  height: 150px;
  background-color: var(--char-yellow);
  border-radius: 50% 50% 0 0;
}

/* === 交互与静态特征 === */
.interactive-features,
.static-features {
  position: absolute;
  top: 40px;
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
}

.static-features {
  flex-direction: row;
  gap: 15px;
  justify-content: center;
}

.eyes-container {
  display: flex;
  gap: 15px;
  transition: opacity 0.2s ease;
}

.eye {
  position: relative;
  width: 32px;
  height: 32px;
  overflow: hidden;
  background-color: #ffffff;
  border-radius: 50%;
  box-shadow: inset 0 2px 5px rgba(0, 0, 0, 0.1);
  transition:
    height 0.2s ease,
    margin-top 0.2s ease,
    background-color 0.2s ease;
}

.pupil {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 14px;
  height: 14px;
  background-color: #111111;
  border-radius: 50%;
  transform: translate(-50%, -50%);
  transition: transform 0.05s ease-out;
}

/* 闭眼状态样式控制 */
.eyes-closed .eyes-container {
  gap: 12px;
}
.eyes-closed .eye {
  height: 4px;
  margin-top: 14px;
  background-color: rgba(255, 255, 255, 0.4);
  border-radius: 2px;
  box-shadow: none;
}
.eyes-closed .pupil {
  display: none;
}

/* === 右侧表单样式 === */
.login-container {
  width: 100%;
  max-width: 440px;
}
h1 {
  margin-bottom: 10px;
  font-size: 2.5rem;
  color: var(--form-text);
}
.subtitle {
  margin-bottom: 35px;
  font-size: 0.95rem;
  color: var(--form-subtitle);
}

.form-group {
  position: relative;
  margin-bottom: 24px;
}
label {
  display: block;
  margin-bottom: 8px;
  font-size: 0.9rem;
  font-weight: bold;
  color: var(--form-text);
}
input[type="email"],
input[type="password"],
input[type="text"] {
  width: 100%;
  padding: 14px 16px;
  font-size: 1rem;
  color: var(--form-text);
  border: 1px solid var(--input-border);
  border-radius: 8px;
  outline: none;
  transition: border-color 0.2s ease;
}
input:focus {
  border-color: var(--primary-purple);
}

.password-toggle {
  position: absolute;
  top: 50%;
  right: 16px;
  display: flex;
  align-items: center;
  color: #777;
  cursor: pointer;
  user-select: none;
  transform: translateY(-50%);
}
.password-toggle svg {
  width: 20px;
  height: 20px;
  fill: none;
}

.btn-primary {
  width: 100%;
  padding: 14px;
  margin-top: 10px;
  font-size: 1rem;
  font-weight: bold;
  color: var(--btn-text);
  cursor: pointer;
  background-color: var(--char-black);
  border: none;
  border-radius: 8px;
  transition: background-color 0.2s ease;
}
.btn-primary:hover {
  background-color: #333;
}
</style>
