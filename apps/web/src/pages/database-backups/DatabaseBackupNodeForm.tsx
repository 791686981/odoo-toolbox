import { Button, Form, Input, Modal, Upload } from "antd";
import type { UploadFile, UploadProps } from "antd";
import { useEffect, useMemo, useState } from "react";

export type DatabaseBackupNodeFormMode = "create-root" | "create-child" | "edit";

export type DatabaseBackupNodeFormValues = {
  name: string;
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
  const [form] = Form.useForm<Omit<DatabaseBackupNodeFormValues, "file">>();
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [selectedFile, setSelectedFile] = useState<File | undefined>();
  const [fileError, setFileError] = useState<string | undefined>();
  const isEdit = mode === "edit";

  useEffect(() => {
    if (!open) {
      form.resetFields();
      setFileList([]);
      setSelectedFile(undefined);
      setFileError(undefined);
      return;
    }

    form.setFieldsValue({
      name: initialValues?.name ?? "",
      note: initialValues?.note ?? "",
    });
    setFileList([]);
    setSelectedFile(undefined);
    setFileError(undefined);
  }, [form, initialValues, open]);

  const title = useMemo(() => {
    if (mode === "edit") {
      return "编辑节点";
    }
    return mode === "create-root" ? "新建根节点" : "新增分支节点";
  }, [mode]);

  const beforeUpload: UploadProps["beforeUpload"] = (file) => {
    setFileList([file]);
    setSelectedFile(file as File);
    setFileError(undefined);
    return false;
  };

  const handleRemove = () => {
    setFileList([]);
    setSelectedFile(undefined);
    return true;
  };

  async function handleOk() {
    const values = await form.validateFields();
    if (!isEdit && !selectedFile) {
      setFileError("请上传 zip 备份文件");
      return;
    }
    await onSubmit({
      ...values,
      file: selectedFile,
    });
  }

  return (
    <Modal
      open={open}
      title={title}
      okText="确认"
      cancelText="取消"
      forceRender
      confirmLoading={submitting}
      onCancel={onCancel}
      onOk={handleOk}
      destroyOnHidden
    >
      <Form form={form} layout="vertical">
        <Form.Item name="name" label="节点名" rules={[{ required: true, message: "请输入节点名" }]}>
          <Input />
        </Form.Item>
        <Form.Item name="note" label="备注">
          <Input.TextArea rows={4} />
        </Form.Item>
        {!isEdit ? (
          <Form.Item
            label="zip 备份文件"
            validateStatus={fileError ? "error" : undefined}
            help={fileError}
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
