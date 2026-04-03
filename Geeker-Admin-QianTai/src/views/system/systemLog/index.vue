<template>
  <div class="table-box">
    <ProTable ref="proTable" :columns="columns" :request-api="getTableList" :data-callback="dataCallback" />

    <el-dialog v-model="detailVisible" title="请求参数详情" width="640px" destroy-on-close append-to-body>
      <el-scrollbar max-height="420px">
        <el-text tag="pre" class="param-pre">{{ detailText || "（空）" }}</el-text>
      </el-scrollbar>
    </el-dialog>
  </div>
</template>

<script setup lang="tsx" name="systemLog">
import { reactive, ref } from "vue";
import ProTable from "@/components/ProTable/index.vue";
import { ColumnProps, ProTableInstance } from "@/components/ProTable/interface";
import { getSystemLogList, type SystemOperLogRow } from "@/api/modules/system";

const proTable = ref<ProTableInstance>();
const detailVisible = ref(false);
const detailText = ref("");

const dataCallback = (data: any) => ({
  list: data.list,
  total: data.total
});

const getTableList = (params: any) => getSystemLogList(JSON.parse(JSON.stringify(params)));

const openParamDetail = (raw: string) => {
  detailText.value = raw || "";
  detailVisible.value = true;
};

const methodTagType = (m: string) => {
  const u = (m || "").toUpperCase();
  if (u === "GET") return "success";
  if (u === "POST") return "primary";
  if (u === "PUT") return "warning";
  if (u === "PATCH") return "warning";
  if (u === "DELETE") return "danger";
  return "info";
};

const columns = reactive<ColumnProps<SystemOperLogRow>[]>([
  { type: "index", label: "#", width: 56 },
  {
    prop: "userName",
    label: "操作人",
    minWidth: 120,
    search: { el: "input" }
  },
  {
    prop: "requestMethod",
    label: "请求方式",
    width: 110,
    search: {
      el: "select",
      props: { filterable: true }
    },
    enum: [
      { label: "POST", value: "POST" },
      { label: "PUT", value: "PUT" },
      { label: "PATCH", value: "PATCH" },
      { label: "DELETE", value: "DELETE" }
    ],
    render: scope => (
      <el-tag type={methodTagType(scope.row.requestMethod)} effect="plain">
        {scope.row.requestMethod || "--"}
      </el-tag>
    )
  },
  {
    prop: "requestUrl",
    label: "请求路径",
    minWidth: 200,
    showOverflowTooltip: true
  },
  {
    prop: "requestParam",
    label: "请求参数",
    minWidth: 200,
    render: scope => {
      const raw = scope.row.requestParam || "";
      const short = raw.length > 72 ? `${raw.slice(0, 72)}…` : raw;
      return (
        <div class="param-cell">
          <span class="param-ellipsis" title={raw}>
            {raw ? short : "—"}
          </span>
          {raw ? (
            <el-button type="primary" link onClick={() => openParamDetail(raw)}>
              查看详情
            </el-button>
          ) : null}
        </div>
      );
    }
  },
  {
    prop: "requestIp",
    label: "操作 IP",
    width: 140
  },
  {
    prop: "executeTime",
    label: "耗时",
    width: 100,
    render: scope => `${scope.row.executeTime ?? 0} ms`
  },
  {
    prop: "status",
    label: "状态",
    width: 90,
    render: scope => (
      <el-tag type={scope.row.status === 1 ? "success" : "danger"}>{scope.row.status === 1 ? "成功" : "失败"}</el-tag>
    )
  },
  {
    prop: "errorMsg",
    label: "错误信息",
    minWidth: 160,
    showOverflowTooltip: true
  },
  {
    prop: "createTime",
    label: "操作时间",
    width: 175
  }
]);
</script>

<style scoped lang="scss">
.param-cell {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}
.param-ellipsis {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.param-pre {
  display: block;
  margin: 0;
  padding: 8px 4px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
