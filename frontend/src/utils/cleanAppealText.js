/** Убирает HTML-теги и лишние пробелы из текста обращения. */
export function cleanAppealText(text) {
  return String(text ?? '')
    .replace(/&nbsp;/gi, ' ')
    .replace(/<br\s*\/?>/gi, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/^['"«»\s]+|['"»\s]+$/g, '')
    .replace(/\s+/g, ' ')
    .trim()
}
