import { Button, Card, Col, Form, Input, InputNumber, Row, Switch, Typography, message } from "antd";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect } from "react";

import { api } from "../../shared/api/client";

type SettingsFormValues = {
  default_source_language: string;
  default_target_language: string;
  default_chunk_size: number;
  default_concurrency: number;
  default_overwrite_existing: boolean;
};

export function SettingsPage() {
  const [form] = Form.useForm<SettingsFormValues>();
  const settingsQuery = useQuery({
    queryKey: ["settings"],
    queryFn: api.settings,
  });

  useEffect(() => {
    if (settingsQuery.data) {
      form.setFieldsValue(settingsQuery.data);
    }
  }, [form, settingsQuery.data]);

  const updateMutation = useMutation({
    mutationFn: api.updateSettings,
    onSuccess: (data) => {
      form.setFieldsValue(data);
      message.success("设置已保存");
    },
    onError: (error: Error) => {
      message.error(error.message);
    },
  });

  return (
    <div className="page-stack">
      <section className="workspace-hero compact">
        <div className="workspace-copy-group">
          <Typography.Title level={2} className="workspace-title">
            系统设置
          </Typography.Title>
        </div>
      </section>

      <Row gutter={[20, 20]}>
        <Col xs={24} lg={9}>
          <Card className="panel-card">
            <Typography.Text className="section-kicker">Runtime</Typography.Text>
            <Typography.Title level={3} className="panel-title">
              当前运行环境
            </Typography.Title>
            <div className="settings-readout">
              <div className="settings-readout-row">
                <span>OpenAI Base URL</span>
                <strong>{settingsQuery.data?.openai_base_url ?? "-"}</strong>
              </div>
              <div className="settings-readout-row">
                <span>翻译模型</span>
                <strong>{settingsQuery.data?.openai_translation_model ?? "-"}</strong>
              </div>
              <div className="settings-readout-row">
                <span>AI 校对模型</span>
                <strong>{settingsQuery.data?.openai_review_model ?? "-"}</strong>
              </div>
              <div className="settings-readout-row">
                <span>默认语言对</span>
                <strong>
                  {settingsQuery.data?.default_source_language ?? "-"} → {settingsQuery.data?.default_target_language ?? "-"}
                </strong>
              </div>
            </div>
          </Card>
        </Col>
        <Col xs={24} lg={15}>
          <Card className="panel-card">
            <Typography.Text className="section-kicker">Defaults</Typography.Text>
            <Typography.Title level={3} className="panel-title">
              任务默认参数
            </Typography.Title>
            <Form form={form} layout="vertical" onFinish={(values) => updateMutation.mutate(values)}>
              <Row gutter={16}>
                <Col xs={24} md={12}>
                  <Form.Item label="默认源语言" name="default_source_language">
                    <Input />
                  </Form.Item>
                </Col>
                <Col xs={24} md={12}>
                  <Form.Item label="默认目标语言" name="default_target_language">
                    <Input />
                  </Form.Item>
                </Col>
                <Col xs={24} md={12}>
                  <Form.Item label="默认分块大小" name="default_chunk_size">
                    <InputNumber min={1} max={200} style={{ width: "100%" }} />
                  </Form.Item>
                </Col>
                <Col xs={24} md={12}>
                  <Form.Item label="默认并发数" name="default_concurrency">
                    <InputNumber min={1} max={10} style={{ width: "100%" }} />
                  </Form.Item>
                </Col>
              </Row>
              <Form.Item label="默认覆盖已有翻译" name="default_overwrite_existing" valuePropName="checked">
                <Switch />
              </Form.Item>
              <Button type="primary" htmlType="submit" loading={updateMutation.isPending}>
                保存设置
              </Button>
            </Form>
          </Card>
        </Col>
      </Row>
    </div>
  );
}
