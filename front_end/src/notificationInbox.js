import React, { useCallback, useEffect, useRef, useState } from 'react';
import { ActivityIndicator, AppState, Pressable, StyleSheet, Text, View } from 'react-native';
import { api } from './api';
import { Button, Field, Notice } from './components';
import { InlineConfirm, ManagementShell } from './managementComponents';
import { canRespondToNotification, formatNotificationDate, notificationStatus } from './notificationUtils';
import { colors } from './theme';

export function useNotificationInbox(enabled) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState(null);
  const [busy, setBusy] = useState(null);
  const [retryResponses, setRetryResponses] = useState({});
  const lifecycle = useRef(0);
  const requestVersion = useRef(0);
  const mutating = useRef(false);

  const refresh = useCallback(async () => {
    if (!enabled || mutating.current) return;
    const cycle = lifecycle.current;
    const version = ++requestVersion.current;
    const current = () => cycle === lifecycle.current && version === requestVersion.current;
    setLoading(true);
    try {
      const result = await api.listNotifications();
      if (current()) {
        setItems(result);
        setLoaded(true);
        setError('');
      }
    } catch (requestError) {
      if (current()) setError(requestError.message);
    } finally {
      if (current()) setLoading(false);
    }
  }, [enabled]);

  useEffect(() => {
    lifecycle.current += 1;
    if (!enabled) {
      setItems([]);
      setLoaded(false);
      setLoading(false);
      setError('');
      setNotice(null);
      setBusy(null);
      setRetryResponses({});
      mutating.current = false;
      return;
    }
    refresh();
    const interval = setInterval(() => {
      if (AppState.currentState === 'active') refresh();
    }, 30000);
    const subscription = AppState.addEventListener('change', (state) => {
      if (state === 'active') refresh();
    });
    return () => {
      lifecycle.current += 1;
      requestVersion.current += 1;
      clearInterval(interval);
      subscription.remove();
    };
  }, [enabled, refresh]);

  const act = async (id, action) => {
    if (!enabled || mutating.current) return false;
    mutating.current = true;
    requestVersion.current += 1; // Uma consulta anterior não pode desfazer a alteração.
    const cycle = lifecycle.current;
    const current = () => cycle === lifecycle.current;
    setLoading(false);
    setBusy({ id, action });
    setNotice(null);
    let reconcile = false;
    const recordDecision = (status, respondedAt) => {
      setItems((previous) => previous.map((item) => item.id === id ? {
        ...item, lida: true, pode_responder: false,
        reagendamento: { ...item.reagendamento, status, respondida_em: respondedAt },
      } : item));
    };
    try {
      if (action === 'delete') {
        await api.deleteNotification(id);
        if (!current()) return false;
        setItems((previous) => previous.filter((item) => item.id !== id));
        setNotice({ text: 'Notificação excluída.' });
      } else {
        const result = await api.respondToNotification(id, action);
        if (!current()) return false;
        recordDecision(result.status, result.respondida_em);
        setNotice({ text: result.message || 'Resposta registrada.' });
      }
      setRetryResponses((previous) => {
        const next = { ...previous };
        delete next[id];
        return next;
      });
      return true;
    } catch (requestError) {
      if (!current()) return false;
      if (action !== 'delete' && requestError.detail?.resposta_salva === true) {
        recordDecision(action, null);
        setRetryResponses((previous) => ({ ...previous, [id]: action }));
      }
      if (requestError.status === 404) {
        setItems((previous) => previous.filter((item) => item.id !== id));
      }
      reconcile = [409, 410].includes(requestError.status);
      setNotice({ type: 'error', text: requestError.message });
      return false;
    } finally {
      if (current()) {
        mutating.current = false;
        setBusy(null);
        if (reconcile) refresh();
      }
    }
  };

  return { items, loading, loaded, error, notice, busy, retryResponses, refresh, act };
}

function BellIcon() {
  return (
    <View style={s.bellIcon} accessible={false}>
      <View style={s.bellHandle} />
      <View style={s.bellBody} />
      <View style={s.bellBase} />
      <View style={s.bellClapper} />
    </View>
  );
}

export function NotificationBell({ inbox, onPress }) {
  const count = inbox.items.length;
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={`Abrir notificações${inbox.loaded ? `, ${count} ${count === 1 ? 'notificação' : 'notificações'}` : ''}`}
      style={({ pressed }) => [s.bellButton, pressed && s.pressed]}
    >
      <BellIcon />
      {count > 0 ? <View style={s.counter}><Text style={s.counterText}>{count > 99 ? '99+' : count}</Text></View> : null}
      {inbox.error ? <View style={s.connectionDot} /> : null}
    </Pressable>
  );
}

const STATUSES = {
  aviso: ['Aviso', 'neutral'],
  pendente: ['Aguardando resposta', 'pending'],
  aceita: ['Aceita', 'accepted'],
  recusada: ['Recusada', 'declined'],
  cancelada: ['Cancelada', 'neutral'],
  expirada: ['Prazo encerrado', 'neutral'],
};

function NotificationCard({ item, inbox, now }) {
  const [expanded, setExpanded] = useState(false);
  const [confirm, setConfirm] = useState(null);
  const retryStatus = inbox.retryResponses[item.id];
  const status = retryStatus || notificationStatus(item, now);
  const [label, tone] = STATUSES[status] || ['Indisponível', 'neutral'];
  const request = item.reagendamento;
  const canRespond = !retryStatus && canRespondToNotification(item, now);
  const disabled = Boolean(inbox.busy);
  const working = inbox.busy?.id === item.id;
  const confirmText = confirm === 'delete'
    ? 'Excluir esta notificação? Isso não cancela nem recusa o pedido de reagendamento.'
    : confirm === 'aceita'
      ? 'Aceitar o novo horário? O aluno será avisado pelo WhatsApp.'
      : 'Recusar este pedido? A aula continuará no horário original e o aluno será avisado pelo WhatsApp.';

  useEffect(() => {
    if (!canRespond && confirm !== 'delete') setConfirm(null);
  }, [canRespond, confirm]);

  const perform = async () => {
    if (confirm !== 'delete' && !canRespondToNotification(item)) {
      setConfirm(null);
      inbox.refresh();
      return;
    }
    const ok = await inbox.act(item.id, confirm);
    if (ok) setConfirm(null);
  };

  return (
    <View style={[s.card, status === 'pendente' && s.pendingCard]}>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`${item.titulo}. ${expanded ? 'Recolher' : 'Ver'} detalhes`}
        accessibilityState={{ expanded }}
        onPress={() => { setExpanded(!expanded); setConfirm(null); }}
        disabled={disabled}
        style={({ pressed }) => [s.cardHeader, pressed && s.pressed]}
      >
        <View style={s.cardContent}>
          <View style={[s.status, s[tone]]}><Text style={[s.statusText, s[`${tone}Text`]]}>{label}</Text></View>
          <Text style={s.cardTitle}>{item.titulo}</Text>
          {item.aluno_nome ? <Text style={s.student}>{item.aluno_nome}</Text> : null}
          <Text style={s.date}>{formatNotificationDate(item.criada_em)}</Text>
        </View>
        <Text style={s.chevron}>{expanded ? '−' : '＋'}</Text>
      </Pressable>
      <Text style={s.message} numberOfLines={expanded ? undefined : 3}>{item.mensagem}</Text>
      {expanded ? (
        <>
          {request ? (
            <View style={s.details}>
              <Text style={s.detailLabel}>AULA ORIGINAL</Text>
              <Text style={s.detailValue}>{formatNotificationDate(request.data_hora_aula_original, 'academy')}</Text>
              <Text style={[s.detailLabel, s.detailSpacing]}>NOVO HORÁRIO</Text>
              <Text style={s.detailValue}>{formatNotificationDate(request.nova_data_hora_inicio, 'academy')}</Text>
              <Text style={s.detailSecondary}>Término: {formatNotificationDate(request.nova_data_hora_fim, 'academy')}</Text>
              {request.motivo ? <><Text style={[s.detailLabel, s.detailSpacing]}>MOTIVO</Text><Text style={s.detailValue}>{request.motivo}</Text></> : null}
              <Text style={s.timezone}>Horários da academia (UTC−3).</Text>
            </View>
          ) : null}
          {canRespond ? <Text style={s.deadline}>Responda até {formatNotificationDate(request.expira_em)}.</Text> : null}
          {status === 'expirada' ? <Text style={s.deadline}>O prazo para responder a esta solicitação terminou.</Text> : null}
          {request?.respondida_em ? <Text style={s.deadline}>Respondida em {formatNotificationDate(request.respondida_em)}.</Text> : null}
          {retryStatus ? (
            <View style={s.retryBox}>
              <Text style={s.retryText}>Sua decisão foi salva. O envio ao WhatsApp ainda não foi confirmado.</Text>
              <Button title="Tentar avisar o aluno novamente" variant="secondary" disabled={disabled} loading={working} onPress={() => inbox.act(item.id, retryStatus)} />
            </View>
          ) : null}
          {canRespond && !confirm ? (
            <View style={s.responseActions}>
              <Button title="Aceitar" style={s.responseButton} disabled={disabled} onPress={() => setConfirm('aceita')} />
              <Button title="Recusar" style={s.responseButton} variant="secondary" disabled={disabled} onPress={() => setConfirm('recusada')} />
            </View>
          ) : null}
        </>
      ) : null}
      {confirm ? (
        <InlineConfirm text={confirmText} loading={working} onCancel={() => setConfirm(null)} onConfirm={perform} />
      ) : (
        <View style={s.cardFooter}>
          <Pressable accessibilityRole="button" disabled={disabled} onPress={() => setExpanded(!expanded)} style={s.textButton}>
            <Text style={s.detailsLink}>{expanded ? 'Recolher' : canRespond ? 'Ver e responder' : 'Ver detalhes'}</Text>
          </Pressable>
          <Pressable accessibilityRole="button" accessibilityLabel={`Excluir notificação: ${item.titulo}`} disabled={disabled} onPress={() => setConfirm('delete')} style={s.textButton}>
            <Text style={s.deleteLink}>Excluir</Text>
          </Pressable>
        </View>
      )}
    </View>
  );
}

export function NotificationsScreen({ inbox, onBack }) {
  const [filter, setFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    inbox.refresh();
    const interval = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(interval);
  }, [inbox.refresh]);
  const normalize = (text) => String(text || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  const term = normalize(search.trim());
  const pendingCount = inbox.items.filter((item) => canRespondToNotification(item, now) && !inbox.retryResponses[item.id]).length;
  const visible = inbox.items.filter((item) => (filter !== 'pending' || (canRespondToNotification(item, now) && !inbox.retryResponses[item.id]))
    && (!term || normalize(`${item.aluno_nome || ''} ${item.titulo} ${item.mensagem}`).includes(term)));

  return (
    <ManagementShell
      title="Notificações"
      subtitle="Acompanhe os avisos e os pedidos dos seus alunos."
      onBack={() => { if (!inbox.busy) onBack(); }}
      action={<Pressable accessibilityRole="button" accessibilityLabel="Atualizar notificações" disabled={inbox.loading || Boolean(inbox.busy)} onPress={inbox.refresh} style={s.textButton}>{inbox.loading ? <ActivityIndicator size="small" color={colors.ink} /> : <Text style={s.detailsLink}>Atualizar</Text>}</Pressable>}
    >
      {inbox.notice ? <Notice type={inbox.notice.type}>{inbox.notice.text}</Notice> : null}
      {inbox.error ? <Notice type="error">{inbox.error}{inbox.loaded ? ' Exibindo a última lista carregada.' : ''}</Notice> : null}
      <View style={s.summary}>
        <View style={s.summaryIcon}><BellIcon /></View>
        <View style={s.cardContent}>
          <Text style={s.summaryTitle}>{pendingCount ? `${pendingCount} ${pendingCount === 1 ? 'pedido aguarda' : 'pedidos aguardam'} sua resposta` : 'Seus avisos em um só lugar'}</Text>
          <Text style={s.summaryText}>Aceite ou recuse os reagendamentos por aqui.</Text>
        </View>
      </View>
      <Field label="Buscar notificações" placeholder="Nome do aluno ou mensagem" value={search} onChangeText={setSearch} />
      <View style={s.filters}>
        {[['all', 'Todas', inbox.items.length], ['pending', 'Pendentes', pendingCount]].map(([value, title, count]) => (
          <Pressable key={value} accessibilityRole="button" accessibilityState={{ selected: filter === value }} onPress={() => setFilter(value)} style={[s.filter, filter === value && s.filterActive]}>
            <Text style={[s.filterText, filter === value && s.filterTextActive]}>{title} · {count}</Text>
          </Pressable>
        ))}
      </View>
      {!inbox.loaded && inbox.loading ? <ActivityIndicator color={colors.ink} style={s.loader} /> : null}
      {!inbox.loaded && inbox.error ? <Button title="Tentar novamente" variant="secondary" onPress={inbox.refresh} loading={inbox.loading} /> : null}
      {inbox.loaded && visible.length === 0 ? (
        <View style={s.empty}>
          <BellIcon />
          <Text style={s.emptyTitle}>{term ? 'Nenhuma notificação encontrada' : filter === 'pending' ? 'Nenhum pedido pendente' : 'Nenhuma notificação por aqui'}</Text>
          <Text style={s.emptyText}>{term ? 'Tente outro nome ou outra palavra.' : filter === 'pending' ? 'Os pedidos que precisam da sua resposta aparecerão aqui.' : 'Quando houver um novo aviso, você poderá consultá-lo nesta tela.'}</Text>
        </View>
      ) : null}
      <View style={s.cards}>{visible.map((item) => <NotificationCard key={item.id} item={item} inbox={inbox} now={now} />)}</View>
    </ManagementShell>
  );
}

const s = StyleSheet.create({
  bellButton: { width: 48, height: 48, borderRadius: 16, backgroundColor: colors.surface, borderColor: colors.line, borderWidth: 1, alignItems: 'center', justifyContent: 'center' },
  bellIcon: { width: 25, height: 28 },
  bellHandle: { position: 'absolute', width: 5, height: 5, borderRadius: 3, backgroundColor: colors.ink, top: 1, left: 10 },
  bellBody: { position: 'absolute', width: 19, height: 18, borderTopLeftRadius: 11, borderTopRightRadius: 11, borderWidth: 2, borderColor: colors.ink, top: 4, left: 3, backgroundColor: colors.surface },
  bellBase: { position: 'absolute', width: 25, height: 2, borderRadius: 1, backgroundColor: colors.ink, top: 21 },
  bellClapper: { position: 'absolute', width: 6, height: 3, borderBottomLeftRadius: 4, borderBottomRightRadius: 4, backgroundColor: colors.ink, top: 25, left: 9.5 },
  counter: { position: 'absolute', right: -6, top: -6, minWidth: 22, height: 22, paddingHorizontal: 5, borderRadius: 12, backgroundColor: colors.primary, borderWidth: 2, borderColor: colors.background, alignItems: 'center', justifyContent: 'center' },
  counterText: { color: colors.ink, fontWeight: '900', fontSize: 10 },
  connectionDot: { position: 'absolute', right: 4, bottom: 4, width: 7, height: 7, borderRadius: 4, backgroundColor: colors.danger },
  pressed: { opacity: 0.65 },
  summary: { flexDirection: 'row', gap: 14, padding: 18, borderRadius: 18, backgroundColor: '#E9EFDF', marginBottom: 24, alignItems: 'center' },
  summaryIcon: { width: 48, height: 48, borderRadius: 15, backgroundColor: colors.surface, alignItems: 'center', justifyContent: 'center' },
  summaryTitle: { color: colors.ink, fontSize: 16, fontWeight: '800', lineHeight: 22 },
  summaryText: { color: colors.muted, lineHeight: 19, fontSize: 13, marginTop: 4 },
  filters: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 18, marginBottom: 22 },
  filter: { paddingHorizontal: 16, paddingVertical: 12, borderRadius: 24, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line },
  filterActive: { backgroundColor: colors.ink, borderColor: colors.ink },
  filterText: { color: colors.muted, fontWeight: '800', fontSize: 13 },
  filterTextActive: { color: colors.primary },
  cards: { gap: 16 },
  card: { padding: 20, borderRadius: 20, borderWidth: 1, borderColor: colors.line, backgroundColor: colors.surface },
  pendingCard: { borderColor: '#B8CC94' },
  cardHeader: { flexDirection: 'row', alignItems: 'center', gap: 16 },
  cardContent: { flex: 1 },
  cardTitle: { color: colors.ink, fontWeight: '900', fontSize: 18, lineHeight: 24, marginTop: 12 },
  student: { color: colors.ink, fontWeight: '700', marginTop: 5 },
  date: { color: colors.muted, fontSize: 12, marginTop: 6 },
  chevron: { color: colors.muted, fontSize: 24 },
  status: { alignSelf: 'flex-start', borderRadius: 8, paddingHorizontal: 9, paddingVertical: 5 },
  statusText: { fontWeight: '800', fontSize: 11 },
  pending: { backgroundColor: '#F5ECCA' }, pendingText: { color: '#765711' },
  accepted: { backgroundColor: colors.successSoft }, acceptedText: { color: colors.success },
  declined: { backgroundColor: colors.dangerSoft }, declinedText: { color: colors.danger },
  neutral: { backgroundColor: '#EDF0EC' }, neutralText: { color: colors.muted },
  message: { color: colors.muted, lineHeight: 22, fontSize: 14, marginTop: 16 },
  details: { padding: 16, backgroundColor: colors.background, borderRadius: 14, marginTop: 18 },
  detailLabel: { color: colors.muted, fontSize: 10, letterSpacing: 1, fontWeight: '900' },
  detailValue: { color: colors.ink, fontSize: 15, fontWeight: '700', lineHeight: 22, marginTop: 6 },
  detailSecondary: { color: colors.muted, fontSize: 13, lineHeight: 20, marginTop: 4 },
  detailSpacing: { marginTop: 18 },
  timezone: { color: colors.muted, fontSize: 11, marginTop: 18 },
  deadline: { color: colors.muted, fontSize: 12, lineHeight: 19, marginTop: 14 },
  responseActions: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginTop: 18 },
  responseButton: { flexGrow: 1, flexBasis: 120 },
  cardFooter: { flexDirection: 'row', justifyContent: 'space-between', borderTopWidth: 1, borderTopColor: colors.line, marginTop: 16, paddingTop: 6, gap: 12 },
  textButton: { minHeight: 44, justifyContent: 'center', paddingHorizontal: 2 },
  detailsLink: { color: colors.ink, fontWeight: '800', fontSize: 13 },
  deleteLink: { color: colors.danger, fontWeight: '700', fontSize: 13 },
  retryBox: { gap: 12, marginTop: 16, padding: 14, borderRadius: 12, backgroundColor: '#FFF5DF' },
  retryText: { color: colors.ink, lineHeight: 21, fontSize: 13 },
  loader: { marginVertical: 40 },
  empty: { alignItems: 'center', paddingVertical: 48, paddingHorizontal: 16 },
  emptyTitle: { fontWeight: '800', fontSize: 18, color: colors.ink, textAlign: 'center', marginTop: 18 },
  emptyText: { color: colors.muted, lineHeight: 22, textAlign: 'center', maxWidth: 340, marginTop: 8 },
});
