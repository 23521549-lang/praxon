# Image `eval` cho lệnh một lệnh (task 13.1): chạy `python -m praxon_core.eval.run_all`.
#
# Python 3.11 slim, đúng lệnh cài như CI (`pip install -r requirements-dev.txt`
# + `pip install -e packages/core -e packages/platform`, cùng file requirements
# đã ghim) để image không lệch khỏi cách cài của CI (13.1 R7).
# Không chứa bí mật: key B2 / key model / mật khẩu DB đều qua env lúc chạy.
# Không chứa git: `code_commit` do wrapper tính trên host rồi truyền qua
# cờ `--code-commit` (run_all tự rơi về "unknown" nếu thiếu).
FROM python:3.11-slim
WORKDIR /app
COPY requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY . .
RUN pip install --no-cache-dir -e packages/core -e packages/platform
ENTRYPOINT ["python", "-m", "praxon_core.eval.run_all"]
