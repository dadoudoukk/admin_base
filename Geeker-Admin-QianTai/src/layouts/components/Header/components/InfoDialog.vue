<template>
  <el-dialog v-model="dialogVisible" title="个人信息" width="500px" draggable>
    <div class="info-wrap">
      <p><strong>用户名：</strong>{{ displayName }}</p>
      <p><strong>角色：</strong>{{ displayRole }}</p>
    </div>
    <template #footer>
      <span class="dialog-footer">
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="dialogVisible = false">确认</el-button>
      </span>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { useUserStore } from "@/stores/modules/user";

const dialogVisible = ref(false);
const userStore = useUserStore();
const displayName = computed(() => userStore.userInfo?.name || "管理员");
const displayRole = computed(() => userStore.userInfo?.roleName || "管理员");
const openDialog = () => {
  dialogVisible.value = true;
};

defineExpose({ openDialog });
</script>

<style scoped>
.info-wrap {
  line-height: 1.9;
}
</style>
