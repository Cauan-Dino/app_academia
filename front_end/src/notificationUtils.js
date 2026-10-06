// A API grava criação/prazos em UTC, mas os horários das aulas em UTC−3.
export function notificationDate(value, source = 'utc') {
  if (!value) return null;
  const text = String(value).replace(' ', 'T');
  const hasOffset = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(text);
  const date = new Date(hasOffset ? text : `${text}${source === 'academy' ? '-03:00' : 'Z'}`);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatNotificationDate(value, source = 'utc') {
  const date = notificationDate(value, source);
  if (!date) return 'Horário indisponível';
  const local = new Date(date.getTime() - 3 * 60 * 60 * 1000);
  const pad = (number) => String(number).padStart(2, '0');
  return `${pad(local.getUTCDate())}/${pad(local.getUTCMonth() + 1)}/${local.getUTCFullYear()} às ${pad(local.getUTCHours())}:${pad(local.getUTCMinutes())}`;
}

export function notificationStatus(item, now = Date.now()) {
  const request = item.reagendamento;
  if (!request) return 'aviso';
  const expires = notificationDate(request.expira_em);
  if (request.status === 'pendente' && expires && expires.getTime() <= now) return 'expirada';
  return request.status;
}

export function canRespondToNotification(item, now = Date.now()) {
  const expires = notificationDate(item.reagendamento?.expira_em);
  return Boolean(item.pode_responder && notificationStatus(item, now) === 'pendente'
    && expires && expires.getTime() > now);
}
