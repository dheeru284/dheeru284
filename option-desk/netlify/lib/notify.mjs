// Phone push for alerts. Two free channels, each enabled by environment variables:
//   ntfy:     NTFY_TOPIC  (install the ntfy app, subscribe to the same topic)
//   Telegram: TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID
const PRIORITY = { EXIT: 'urgent', STOP: 'urgent', WARN: 'high', TARGET: 'high', INFO: 'default', TEST: 'default' };
const EMOJI = { EXIT: 'rotating_light', STOP: 'rotating_light', WARN: 'warning', TARGET: 'white_check_mark', INFO: 'newspaper', TEST: 'bell' };

export async function push(alert) {
  const sent = [], errors = [];
  const title = `${alert.level}: ${alert.title}`.slice(0, 250);
  const topic = process.env.NTFY_TOPIC;
  if (topic) {
    try {
      const r = await fetch(`https://ntfy.sh/${encodeURIComponent(topic)}`, {
        method: 'POST', body: alert.body || alert.title,
        headers: { Title: title.replace(/[^\x20-\x7E]/g, ''), Priority: PRIORITY[alert.level] || 'default', Tags: EMOJI[alert.level] || 'bell',
          ...(alert.url ? { Click: alert.url } : {}) },
        signal: AbortSignal.timeout(6000),
      });
      r.ok ? sent.push('ntfy') : errors.push(`ntfy ${r.status}`);
    } catch (e) { errors.push(`ntfy ${e.message}`); }
  }
  const tok = process.env.TELEGRAM_BOT_TOKEN, chat = process.env.TELEGRAM_CHAT_ID;
  if (tok && chat) {
    try {
      const r = await fetch(`https://api.telegram.org/bot${tok}/sendMessage`, {
        method: 'POST', headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ chat_id: chat, text: `${title}\n\n${alert.body || ''}`.slice(0, 4000), disable_web_page_preview: true }),
        signal: AbortSignal.timeout(6000),
      });
      r.ok ? sent.push('telegram') : errors.push(`telegram ${r.status}`);
    } catch (e) { errors.push(`telegram ${e.message}`); }
  }
  if (!topic && !(tok && chat)) errors.push('no push channel configured (set NTFY_TOPIC or TELEGRAM_*)');
  return { sent, errors };
}
