# Chạy mô hình nhỏ trên CPU: llama-server + Qwen3-8B-GGUF (task 6.1)

Hướng dẫn chạy backend CPU hằng ngày của task 6.1: mô hình Qwen3-8B
(Apache-2.0) chạy trên `llama-server` (llama.cpp, MIT) tại
`http://localhost:8080/v1`. Adapter `praxon_core.adapters.language_model`
nói chuyện với server này qua SDK `openai`; không cần GPU, không tiêu hạn
mức GPU nào (spec dòng 223).

## 1. Tải model (một lần, ngoài kho)

- Kho Hugging Face: `Qwen/Qwen3-8B-GGUF` (công khai, **không cần token**).
- Tệp: `Qwen3-8B-Q4_K_M.gguf` — 5.027.783.488 byte (~5,03 GB), chạy cần
  ~6,5 GB RAM.
- Revision đã ghim (mặc định của `model_revision` trong Settings): commit
  `7c41481f57cb95916b40956ab2f0b139b296d974` của kho (kiểm ngày 7/11/2026;
  tệp trong commit này có blob `d4ee8ae7f4de3a5046b1a29776a3f011ba28017e`).
  Đổi revision thì đổi cả `model_revision` — nếu không, `run` ghi không tái
  lập được (spec dòng 191).
- Lưu ngoài kho, theo quy ước cache lúc chạy (như log BPIC 2015 ở
  `~/.cache/praxon/bpic2015`): ví dụ `~/.cache/praxon/qwen3-8b/`.
  **Không commit tệp model vào kho.**
- Cách tải (chọn một):
  - `huggingface-cli download Qwen/Qwen3-8B-GGUF Qwen3-8B-Q4_K_M.gguf`
    (cần gói `huggingface-hub`; tải đúng revision đã ghim bằng
    `--revision 7c41481f57cb95916b40956ab2f0b139b296d974`), hoặc
  - để `llama-server` tự tải: `llama-server -hf Qwen/Qwen3-8B-GGUF:Q4_K_M`
    (server tải tệp về cache của nó; kiểm lại blob sau khi tải).

## 2. Chạy server

Cần binary `llama-server` (lấy từ release của llama.cpp,
<https://github.com/ggml-org/llama.cpp/releases>, hoặc build từ nguồn).

```sh
llama-server -m ~/.cache/praxon/qwen3-8b/Qwen3-8B-Q4_K_M.gguf
```

Mặc định server nghe tại `http://localhost:8080/v1` — đúng giá trị mặc định
của `openai_base_url` và `cpu_model_base_url` trong Settings. Chạy ở cổng
khác thì ghi đè bằng tệp TOML hoặc biến môi trường `PRAXON_CPU_MODEL_BASE_URL`.

Kiểm server đã lên chưa (không cần model thật trong CI — test hợp đồng dùng
server giả; đây là kiểm tay ở máy dev):

```sh
curl -s http://localhost:8080/v1/models
```

## 3. Cấu hình (không hard-code credential)

Adapter đọc cấu hình từ `Settings` (tệp TOML + biến môi trường `PRAXON_*`).
Các trường của task 6.1 (mặc định đã là backend CPU; chỉ ghi đè khi cần):

| Trường | Mặc định | Ghi đè |
| --- | --- | --- |
| `openai_base_url` | `http://localhost:8080/v1` | `PRAXON_OPENAI_BASE_URL` |
| `cpu_model_base_url` | `http://localhost:8080/v1` | `PRAXON_CPU_MODEL_BASE_URL` |
| `model_id` | `Qwen/Qwen3-8B-GGUF` | `PRAXON_MODEL_ID` |
| `model_revision` | `7c41481f…` (xem §1) | `PRAXON_MODEL_REVISION` |
| `openai_api_key` | `None` | **chỉ** `PRAXON_OPENAI_API_KEY` |
| `model_max_retries` | `3` | `PRAXON_MODEL_MAX_RETRIES` |
| `model_retry_base_delay_seconds` | `1.0` | `PRAXON_MODEL_RETRY_BASE_DELAY_SECONDS` |

- Backend CPU không yêu cầu xác thực: adapter dùng khóa giả `"local"`.
- Backend endpoint (URL + khóa thật do Thuận cấp): đặt `openai_base_url`
  và `PRAXON_OPENAI_API_KEY` ở môi trường chạy. **Không bao giờ ghi khóa
  vào tệp TOML commit lên kho.**
- Cùng một adapter trỏ tới vLLM trên Kaggle GPU chỉ bằng cách đổi
  `base_url` (spec dòng 223) — không cần thêm code.

## 4. Tính xác định

- `temperature=0` + `seed` cố định cho mỗi lần gọi (tham số giải mã của
  `complete`); cùng seed + đầu vào + phiên bản model thì cùng kết quả
  (spec dòng 191). Test hợp đồng có ca xác định bắt biến động.
- Qwen3 có chế độ thinking (suy luận) làm đầu ra biến động: dùng chế độ
  non-thinking (xem đề xuất 6.1, rủi ro #2). Cách bật/tắt tùy theo template
  chat của llama-server ở thời điểm chạy — kiểm bằng test xác định và bằng
  lần chạy kiểm tích hợp với server thật, rồi ghi lại cách làm đúng ở đây.
- Đã kiểm (7/11/2026, task 6.5, llama-server build 12177): template chat
  của model có biến `enable_thinking` (mặc định bật — model sinh khối
  `<think>` dài hàng trăm token trước đáp án; một lần gọi thử bị hủy ở
  358 token sinh ra mà chưa xong, ~6 phút). Tắt bằng cờ khởi động server:
  `--chat-template-kwargs '{"enable_thinking": false}'` — sau đó model trả
  JSON ngắn đúng schema (11 token) trong ~35 giây và cùng seed cho cùng
  kết quả (kiểm 2 lần gọi giống hệt nhau). Chạy server đo 6.5 phải có cờ
  này, nếu không mỗi câu tốn hàng phút và đáp án bị khối think làm loãng.

## 5. Khi server lỗi

- Server chưa chạy: adapter thử lại `model_max_retries` lần có giãn cách
  rồi báo hỏng bằng `ModelCallError` (spec dòng 219) — bên gọi đánh dấu cả
  lô thất bại, không nuốt lỗi, không trả phản hồi giả.
- Server trả JSON không khớp schema yêu cầu: adapter kiểm lại ở phía host
  và báo hỏng (llama-server bỏ qua lặng lẽ tính năng schema nó không hỗ
  trợ — đề xuất 6.1, rủi ro #3). Schema của Reflector (6.2) chỉ dùng tập
  con được hỗ trợ (object/array/string/number/integer/boolean/null, enum,
  const, required, additionalProperties, min/max).
- Endpoint thật (backend 2) chưa được kiểm ở task 6.1 (URL + khóa do Thuận
  cấp sau): test hợp đồng cho backend 2 dùng server giả; kiểm với endpoint
  thật làm sau khi có URL + khóa.
