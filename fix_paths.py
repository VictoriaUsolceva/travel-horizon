import os
import re
from pathlib import Path

# =====================================================================
# НАСТРОЙКИ
# =====================================================================
# True  — режим проверки (ничего не меняет, только показывает в консоли)
# False — рабочий режим (сразу перезаписывает пути в файлах)
DRY_RUN = False
# =====================================================================


def get_relative_path(
    current_file: Path, target_abs_url: str, root_dir: Path
) -> str:
    """Вычисляет правильный относительный путь от текущего файла до цели."""
    # 1. Отделяем якоря (#top) и параметры (?v=1.2), чтобы не сломать поиск файла
    clean_url = target_abs_url.split("#")[0].split("?")[0]
    suffix = target_abs_url[len(clean_url) :]

    # 2. Убираем начальный слэш "/"
    rel_from_root = clean_url.lstrip("/")

    # 3. Если ссылка вела просто на главную "/", направляем на index.html
    if not rel_from_root:
        target_path = root_dir / "index.html"
    else:
        target_path = root_dir / rel_from_root

    # 4. Считаем путь от папки текущего файла до целевого файла
    rel_path = os.path.relpath(target_path, start=current_file.parent)

    # 5. Меняем обратные слэши Windows (\) на стандартные веб-слэши (/)
    rel_path = rel_path.replace("\\", "/")

    return rel_path + suffix


def process_project():
    # Автоматически определяем папку, в которой лежит сам скрипт
    root_path = Path(__file__).resolve().parent
    script_name = Path(__file__).name

    print(f"Запуск анализа в папке: {root_path}")
    if DRY_RUN:
        print("ВКЛЮЧЕН ТЕСТОВЫЙ РЕЖИМ (DRY_RUN = True). Файлы не изменятся.\n")

    # Регулярные выражения для поиска путей с "/"
    # Игнорируют внешние ссылки вида "//site.ru" (два слэша подряд)
    attr_pattern = re.compile(
        r"""\b(href|src|poster|data-src)=(["'])(/(?!/)[^"']*)\2""", re.IGNORECASE
    )
    css_url_pattern = re.compile(
        r"""url\(\s*(["']?)(/(?!/)[^)"']+)\1\s*\)""", re.IGNORECASE
    )
    srcset_pattern = re.compile(r"""\bsrcset=(["'])([^"']+)\1""", re.IGNORECASE)

    files_changed = 0
    total_replacements = 0

    # Обходим все файлы в папке и подпапках
    for file_path in root_path.rglob("*"):
        # Пропускаем папки и сам файл скрипта
        if not file_path.is_file() or file_path.name == script_name:
            continue

        ext = file_path.suffix.lower()
        # Работаем только с HTML и CSS файлами
        if ext not in [".html", ".htm", ".css"]:
            continue

        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            print(f"Пропущен (не UTF-8): {file_path.relative_to(root_path)}")
            continue

        original_content = content
        file_logs = []

        def log_and_return(old_url, new_url):
            if old_url != new_url:
                file_logs.append(f"   {old_url}  --->  {new_url}")
            return new_url

        # 1. Обработка CSS-файлов (только конструкции url(...))
        if ext == ".css":

            def replace_css(match):
                quote, url = match.group(1), match.group(2)
                new_url = get_relative_path(file_path, url, root_path)
                log_and_return(url, new_url)
                return f"url({quote}{new_url}{quote})"

            content = css_url_pattern.sub(replace_css, content)

        # 2. Обработка HTML-файлов (атрибуты, srcset и инлайн-стили)
        else:

            def replace_attr(match):
                attr, quote, url = match.group(1), match.group(2), match.group(3)
                new_url = get_relative_path(file_path, url, root_path)
                log_and_return(url, new_url)
                return f"{attr}={quote}{new_url}{quote}"

            def replace_inline_css(match):
                quote, url = match.group(1), match.group(2)
                new_url = get_relative_path(file_path, url, root_path)
                log_and_return(url, new_url)
                return f"url({quote}{new_url}{quote})"

            def replace_srcset(match):
                quote, srcset_val = match.group(1), match.group(2)
                parts = []
                for item in srcset_val.split(","):
                    item_stripped = item.strip()
                    if not item_stripped:
                        continue
                    tokens = item_stripped.split()
                    url = tokens[0]
                    if url.startswith("/") and not url.startswith("//"):
                        new_url = get_relative_path(file_path, url, root_path)
                        log_and_return(url, new_url)
                        tokens[0] = new_url
                    parts.append(" ".join(tokens))
                return f"srcset={quote}{', '.join(parts)}{quote}"

            content = attr_pattern.sub(replace_attr, content)
            content = css_url_pattern.sub(replace_inline_css, content)
            content = srcset_pattern.sub(replace_srcset, content)

        # Если в файле нашлись пути для замены
        if content != original_content:
            files_changed += 1
            total_replacements += len(file_logs)
            rel_file_name = file_path.relative_to(root_path)

            print(f"Файл: {rel_file_name} (замен: {len(file_logs)})")
            for log_line in file_logs:
                print(log_line)
            print("-" * 50)

            # Сохраняем изменения, если не включен тестовый режим
            if not DRY_RUN:
                file_path.write_text(content, encoding="utf-8")

    # Итоговая статистика
    print("\nГотово!")
    print(f"Изменено файлов: {files_changed}")
    print(f"Всего исправлено ссылок: {total_replacements}")


if __name__ == "__main__":
    process_project()
