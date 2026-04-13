<template>
  <div class="table-box">
    <el-card shadow="hover" v-loading="loading">
      <template #header>
        <span>全局配置</span>
      </template>
      <el-form v-if="state.list.length" :model="state" label-width="140px">
        <el-form-item
          v-for="(row, index) in state.list"
          :key="row.configKey"
          :label="row.configName"
          :prop="`list.${index}.configValue`"
        >
          <el-input v-if="row.configType === 'text'" v-model="row.configValue" clearable placeholder="请输入" />
          <UploadImg
            v-else-if="row.configType === 'image'"
            v-model:image-url="row.configValue"
            :api="uploadImg"
            height="120px"
            width="120px"
          />
          <el-switch
            v-else-if="row.configType === 'boolean'"
            v-model="row.configValue"
            active-value="true"
            inactive-value="false"
          />
          <el-input v-else v-model="row.configValue" clearable placeholder="请输入" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="saving" @click="handleSave">保存配置</el-button>
        </el-form-item>
      </el-form>
      <el-empty v-else-if="!loading" description="暂无配置项" />
    </el-card>
  </div>
</template>

<script setup lang="ts" name="systemConfig">
import { reactive, ref, onMounted } from "vue";
import { ElMessage } from "element-plus";
import { getSysConfigAll, updateSysConfigBatch } from "@/api/modules/sysConfig";
import { uploadImg } from "@/api/modules/upload";
import { useGlobalStore } from "@/stores/modules/global";
import UploadImg from "@/components/Upload/Img.vue";

interface ConfigFormRow {
  configKey: string;
  configName: string;
  configValue: string;
  configType: string;
}

const globalStore = useGlobalStore();
const loading = ref(false);
const saving = ref(false);

const state = reactive<{ list: ConfigFormRow[] }>({
  list: []
});

const normalizeList = (raw: unknown[]): ConfigFormRow[] => {
  return raw.map((item: any) => {
    const configType = String(item.configType ?? item.config_type ?? "text");
    let configValue = item.configValue != null || item.config_value != null ? String(item.configValue ?? item.config_value) : "";
    if (configType === "boolean" && configValue !== "true" && configValue !== "false") {
      configValue = "false";
    }
    return {
      configKey: String(item.configKey ?? item.config_key ?? ""),
      configName: String(item.configName ?? item.config_name ?? ""),
      configValue,
      configType
    };
  });
};

const loadList = async () => {
  loading.value = true;
  try {
    const res = await getSysConfigAll();
    const raw = (res.data?.list as unknown[]) ?? [];
    state.list = normalizeList(raw);
  } finally {
    loading.value = false;
  }
};

const handleSave = async () => {
  saving.value = true;
  try {
    await updateSysConfigBatch({
      items: state.list.map(r => ({
        config_key: r.configKey,
        config_value: r.configValue
      }))
    });
    ElMessage.success("保存成功");
    await globalStore.initSysConfig();
  } catch {
    /* 错误由 axios 拦截器提示 */
  } finally {
    saving.value = false;
  }
};

onMounted(() => {
  loadList();
});
</script>
