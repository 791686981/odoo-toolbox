import { Button, Form, Input, Modal, Upload } from "antd";
import type { UploadFile, UploadProps } from "antd";
import { useEffect, useMemo, useState } from "react";

export type DatabaseBackupNodeFormMode = "create-root" | "create-child" | "edit";

export type DatabaseBackupNodeFormValues = {
  name: string;
  database_name: string;
  odoo_version: string;
  note: string;
  file?: File;
};

type Props = {
  mode: DatabaseBackupNodeFormMode;
  open: boolean;
  initialValues?: Partial<DatabaseBackupNodeFormValues>;
  submitting: boolean;
  onCancel: () => void;
  onSubmit: (values: DatabaseBackupNodeFormValues) => Promise<void>;
};

export function DatabaseBackupNodeForm(props: Props) {
  const { mode, open, initialValues, submitting, onCancel, onSubmit } = props;
  const [form] = Form.useForm<DatabaseBackupNodeFormValues>();
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const isEdit = mode === "edit";

  useEffect(() => {
    if (!open) {
      form.resetFields();
      setFileList([]);
      return;
    }

    form.setFieldsValue({
      name: initialValues?.name ?? "",
      database_name: initialValues?.database_name ?? "",
      odoo_version: initialValues?.odoo_version ?? "",
      note: initialValues?.note ?? "",
      file: undefined,
    });
    setFileList([]);
  }, [form, initialValues, open]);

  const title = useMemo(() => {
    if (mode === "edit") {
      return "编辑节点";
    }
    return mode === "create-root" ? "新建根节点" : "新增子节点";
  }, [mode]);

  const beforeUpload: UploadProps["beforeUpload"] = (file) => {
    setFileList([file]);
    form.setFieldValue("file", file as File);
    return false;
  };

  const handleRemove = () => {
    setFileList([]);
    form.setFieldValue("file", undefined);
    return true;
  };

  return (
    <Modal
      open={open}
      title={title}
      okText="确认"
      cancelText="取消"
      forceRender
      confirmLoading={submitting}
      onCancel={onCancel}
      onOk={() => form.submit()}
      destroyOnHidden
    >
      <Form form={form} layout="vertical" onFinish={onSubmit}>
        <Form.Item name="name" label="节点名" rules={[{ required: true, message: "请输入节点名" }]}>
          <Input />
        </Form.Item>
        <Form.Item
          name="database_name"
          label="数据库名"
          rules={[{ required: !isEdit, message: "请输入数据库名" }]}
        >
          <Input disabled={isEdit} />
        </Form.Item>
        <Form.Item
          name="odoo_version"
          label="Odoo 版本"
          rules={[{ required: !isEdit, message: "请输入 Odoo 版本" }]}
        >
          <Input disabled={isEdit} />
        </Form.Item>
        <Form.Item name="note" label="备注">
          <Input.TextArea rows={4} />
        </Form.Item>
        {!isEdit ? (
          <Form.Item
            name="file"
            label="zip 备份文件"
            rules={[{ required: true, message: "请上传 zip 备份文件" }]}
          >
            <Upload beforeUpload={beforeUpload} onRemove={handleRemove} fileList={fileList} maxCount={1} accept=".zip">
              <Button>选择 zip 文件</Button>
            </Upload>
          </Form.Item>
        ) : null}
      </Form>
    </Modal>
  );
}
