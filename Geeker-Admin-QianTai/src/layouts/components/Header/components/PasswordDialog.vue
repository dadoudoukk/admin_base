<template>
  <el-dialog v-model="dialogVisible" title="修改密码" width="500px" draggable @closed="resetForm">
    <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
      <el-form-item label="旧密码" prop="oldPassword">
        <el-input v-model="form.oldPassword" type="password" show-password autocomplete="off" placeholder="请输入当前密码" />
      </el-form-item>
      <el-form-item label="新密码" prop="newPassword">
        <el-input v-model="form.newPassword" type="password" show-password autocomplete="off" placeholder="请输入新密码" />
      </el-form-item>
      <el-form-item label="确认密码" prop="confirmPassword">
        <el-input
          v-model="form.confirmPassword"
          type="password"
          show-password
          autocomplete="off"
          placeholder="请再次输入新密码"
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <span class="dialog-footer">
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="loading" @click="submit">确认</el-button>
      </span>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive } from "vue";
import { useRouter } from "vue-router";
import type { ElForm } from "element-plus";
import { ElMessage } from "element-plus";
import { LOGIN_URL } from "@/config";
import { changePasswordApi } from "@/api/modules/login";
import { useUserStore } from "@/stores/modules/user";

const router = useRouter();
const userStore = useUserStore();

const dialogVisible = ref(false);
const loading = ref(false);
const formRef = ref<InstanceType<typeof ElForm>>();

const form = reactive({
  oldPassword: "",
  newPassword: "",
  confirmPassword: ""
});

const validateConfirm = (_rule: unknown, value: string, callback: (e?: Error) => void) => {
  if (value !== form.newPassword) {
    callback(new Error("两次输入的新密码不一致"));
  } else {
    callback();
  }
};

const rules = {
  oldPassword: [{ required: true, message: "请输入旧密码", trigger: "blur" }],
  newPassword: [{ required: true, message: "请输入新密码", trigger: "blur" }],
  confirmPassword: [
    { required: true, message: "请确认新密码", trigger: "blur" },
    { validator: validateConfirm, trigger: "blur" }
  ]
};

const resetForm = () => {
  form.oldPassword = "";
  form.newPassword = "";
  form.confirmPassword = "";
  formRef.value?.resetFields();
};

const submit = () => {
  formRef.value?.validate(async valid => {
    if (!valid) return;
    loading.value = true;
    try {
      const res = await changePasswordApi({
        oldPassword: form.oldPassword,
        newPassword: form.newPassword
      });
      ElMessage.success(res.msg || "密码修改成功，请重新登录");
      dialogVisible.value = false;
      userStore.setToken("");
      userStore.setUserInfo({ name: "Geeker" });
      router.replace(LOGIN_URL);
    } finally {
      loading.value = false;
    }
  });
};

const openDialog = () => {
  dialogVisible.value = true;
};

defineExpose({ openDialog });
</script>
