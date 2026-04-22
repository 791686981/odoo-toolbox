import { Button, Form, Input, Modal, Typography } from "antd";
import { useEffect, useMemo, useRef, useState, type ChangeEvent } from "react";

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
  const [selectedFile, setSelectedFile] = useState<File | undefined>();
  const [fileError, setFileError] = useState<string | undefined>();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const isEdit = mode === "edit";

  useEffect(() => {
    if (!open) {
      form.resetFields();
      setSelectedFile(undefined);
      setFileError(undefined);
      return;
    }

    form.setFieldsValue({
      name: initialValues?.name ?? "",
      note: initialValues?.note ?? "",
    });
    setSelectedFile(undefined);
    setFileError(undefined);
  }, [form, initialValues, open]);

  const title = useMemo(() => {
    if (mode === "edit") {
      return "编辑节点";
    }
    return mode === "create-root" ? "新建根节点" : "新增分支节点";
  }, [mode]);

  function handleOpenFilePicker() {
    fileInputRef.current?.click();
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    setSelectedFile(file);
    setFileError(undefined);
  }

  const handleRemove = () => {
    setSelectedFile(undefined);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
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
            <input
              ref={fileInputRef}
              type="file"
              accept=".zip"
              hidden
              onChange={handleFileChange}
            />
            <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
              <Button onClick={handleOpenFilePicker}>选择 zip 文件</Button>
              {selectedFile ? (
                <>
                  <Typography.Text>{selectedFile.name}</Typography.Text>
                  <Button type="link" onClick={handleRemove}>
                    移除
                  </Button>
                </>
              ) : (
                <Typography.Text type="secondary">请选择一个数据库 zip 备份文件</Typography.Text>
              )}
            </div>
          </Form.Item>
        ) : null}
      </Form>
    </Modal>
  );
}
