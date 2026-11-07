# Entrypoint của service `model` trong compose.yml.
#
# File này được mount vào container (`./tools/model-entrypoint.sh:/entrypoint.sh:ro`)
# và chạy bằng `sh /entrypoint.sh` — KHÔNG viết lại thành `command:` dạng chuỗi:
# Compose tách chuỗi `command:` thành từng từ nên container chỉ chạy lệnh `set`
# rồi thoát 0. Nội dung file mount không qua nội suy của Compose nên
# `$PRAXON_LLM_API_KEY` viết MỘT dấu `$` (viết `$$` trong shell thành PID +
# chuỗi, làm hỏng key). TUYỆT ĐỐI KHÔNG bật chế độ trace từng lệnh (in key ra log CI).
set -e
if [ ! -f /models/Qwen3-8B-Q4_K_M.gguf ]; then
  if command -v curl >/dev/null 2>&1; then
    curl -L -o /models/Qwen3-8B-Q4_K_M.gguf https://huggingface.co/Qwen/Qwen3-8B-GGUF/resolve/7c41481f57cb95916b40956ab2f0b139b296d974/Qwen3-8B-Q4_K_M.gguf
  elif command -v wget >/dev/null 2>&1; then
    wget -O /models/Qwen3-8B-Q4_K_M.gguf https://huggingface.co/Qwen/Qwen3-8B-GGUF/resolve/7c41481f57cb95916b40956ab2f0b139b296d974/Qwen3-8B-Q4_K_M.gguf
  else
    echo 'can curl hoac wget de tai model' >&2; exit 1
  fi
fi
echo 'd98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785  /models/Qwen3-8B-Q4_K_M.gguf' | sha256sum -c -
SERVER_BIN=/app/llama-server
if [ ! -x "$SERVER_BIN" ]; then SERVER_BIN=llama-server; fi
exec "$SERVER_BIN" -m /models/Qwen3-8B-Q4_K_M.gguf --ctx-size 8192 --chat-template-kwargs '{"enable_thinking": false}' --api-key "$PRAXON_LLM_API_KEY" --port 8080 --host 0.0.0.0
