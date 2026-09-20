import React from 'react';
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { colors } from './theme';

export const DAYS = [
  ['segunda', 'Seg'],
  ['terca', 'Ter'],
  ['quarta', 'Qua'],
  ['quinta', 'Qui'],
  ['sexta', 'Sex'],
  ['sabado', 'Sáb'],
  ['domingo', 'Dom'],
];

export const DAY_LABELS = {
  segunda: 'Segunda-feira',
  terca: 'Terça-feira',
  quarta: 'Quarta-feira',
  quinta: 'Quinta-feira',
  sexta: 'Sexta-feira',
  sabado: 'Sábado',
  domingo: 'Domingo',
};

export function shortTime(value) {
  return String(value || '').slice(0, 5);
}

export function ManagementShell({ title, subtitle, onBack, action, children, refreshing }) {
  return (
    <SafeAreaView style={styles.safe}>
      <KeyboardAvoidingView style={styles.flex} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={styles.scroll}>
          <View style={styles.topRow}>
            <Pressable onPress={onBack} hitSlop={10}><Text style={styles.back}>‹ Voltar</Text></Pressable>
            {action || null}
          </View>
          <View style={styles.heading}>
            <Text style={styles.title}>{title}</Text>
            {subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}
          </View>
          {refreshing ? <ActivityIndicator color={colors.primaryDark} style={styles.loader} /> : children}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

export function EmptyState({ title, text, action }) {
  return (
    <View style={styles.empty}>
      <View style={styles.emptyIcon}><Text style={styles.emptyMark}>＋</Text></View>
      <Text style={styles.emptyTitle}>{title}</Text>
      <Text style={styles.emptyText}>{text}</Text>
      {action || null}
    </View>
  );
}

export function Stat({ value, label }) {
  return <View style={styles.stat}><Text style={styles.statValue}>{value}</Text><Text style={styles.statLabel}>{label}</Text></View>;
}

export function DayPicker({ value, onChange, allowAll = false }) {
  const options = allowAll ? [['', 'Todos'], ...DAYS] : DAYS;
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.days}>
      {options.map(([key, label]) => {
        const active = value === key;
        return <Pressable key={key || 'all'} onPress={() => onChange(key)} style={[styles.day, active && styles.dayActive]}><Text style={[styles.dayText, active && styles.dayTextActive]}>{label}</Text></Pressable>;
      })}
    </ScrollView>
  );
}

export function InlineConfirm({ text, onCancel, onConfirm, loading }) {
  return (
    <View style={styles.confirm}>
      <Text style={styles.confirmText}>{text}</Text>
      <View style={styles.confirmActions}>
        <Pressable onPress={onCancel} disabled={loading}><Text style={styles.cancel}>Cancelar</Text></Pressable>
        <Pressable onPress={onConfirm} disabled={loading} style={styles.confirmButton}>
          {loading ? <ActivityIndicator color="#FFF" size="small" /> : <Text style={styles.confirmButtonText}>Confirmar</Text>}
        </Pressable>
      </View>
    </View>
  );
}

export const managementStyles = StyleSheet.create({
  toolbar: { flexDirection: 'row', gap: 10, marginBottom: 18 },
  grow: { flex: 1 },
  cards: { gap: 12 },
  card: { backgroundColor: colors.surface, borderColor: colors.line, borderWidth: 1, borderRadius: 18, padding: 18 },
  cardPressed: { opacity: 0.72 },
  cardTop: { flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 },
  cardTitle: { flex: 1, color: colors.ink, fontSize: 18, lineHeight: 23, fontWeight: '900' },
  cardText: { color: colors.muted, fontSize: 14, lineHeight: 20, marginTop: 6 },
  badge: { alignSelf: 'flex-start', borderRadius: 999, paddingHorizontal: 10, paddingVertical: 6, backgroundColor: '#EEF5DC' },
  badgeText: { color: '#58780B', fontWeight: '900', fontSize: 11 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  between: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 12 },
  divider: { height: 1, backgroundColor: colors.line, marginVertical: 15 },
  link: { color: colors.primaryDark, fontWeight: '900' },
  dangerLink: { color: colors.danger, fontWeight: '800' },
  sectionTitle: { color: colors.ink, fontSize: 18, fontWeight: '900', marginTop: 24, marginBottom: 12 },
  helper: { color: colors.muted, fontSize: 13, lineHeight: 19, marginTop: 7 },
  twoColumns: { flexDirection: 'row', gap: 12 },
  half: { flex: 1 },
  meta: { color: colors.muted, fontSize: 13, fontWeight: '700' },
  count: { color: colors.ink, fontWeight: '900' },
  participant: { backgroundColor: colors.surface, borderColor: colors.line, borderWidth: 1, borderRadius: 15, padding: 15, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: 12 },
  participantInfo: { flex: 1 },
  participantName: { color: colors.ink, fontWeight: '800', fontSize: 16 },
  participantPhone: { color: colors.muted, marginTop: 4 },
});

const styles = StyleSheet.create({
  flex: { flex: 1 },
  safe: { flex: 1, backgroundColor: colors.background },
  scroll: { flexGrow: 1, width: '100%', maxWidth: 820, alignSelf: 'center', padding: 24, paddingBottom: 60 },
  topRow: { minHeight: 58, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  back: { color: colors.ink, fontSize: 16, fontWeight: '800' },
  heading: { marginBottom: 24 },
  title: { color: colors.ink, fontSize: 31, lineHeight: 37, fontWeight: '900', letterSpacing: -0.8 },
  subtitle: { color: colors.muted, fontSize: 15, lineHeight: 22, marginTop: 7 },
  loader: { marginTop: 80 },
  empty: { alignItems: 'center', paddingVertical: 54, paddingHorizontal: 24 },
  emptyIcon: { width: 58, height: 58, borderRadius: 20, backgroundColor: '#E9ECE8', alignItems: 'center', justifyContent: 'center', marginBottom: 18 },
  emptyMark: { color: colors.muted, fontSize: 28, fontWeight: '500' },
  emptyTitle: { color: colors.ink, fontSize: 19, fontWeight: '900', textAlign: 'center' },
  emptyText: { color: colors.muted, lineHeight: 21, textAlign: 'center', maxWidth: 390, marginTop: 8, marginBottom: 18 },
  stat: { flex: 1, backgroundColor: '#E9ECE8', borderRadius: 15, padding: 15 },
  statValue: { color: colors.ink, fontWeight: '900', fontSize: 21 },
  statLabel: { color: colors.muted, fontWeight: '700', fontSize: 12, marginTop: 3 },
  days: { gap: 8, paddingBottom: 6 },
  day: { minWidth: 52, alignItems: 'center', borderRadius: 999, borderWidth: 1, borderColor: colors.line, paddingHorizontal: 13, paddingVertical: 10, backgroundColor: colors.surface },
  dayActive: { backgroundColor: colors.ink, borderColor: colors.ink },
  dayText: { color: colors.muted, fontWeight: '800', fontSize: 13 },
  dayTextActive: { color: colors.primary },
  confirm: { backgroundColor: colors.dangerSoft, borderColor: '#F0CACA', borderWidth: 1, borderRadius: 15, padding: 15, marginTop: 14 },
  confirmText: { color: colors.ink, lineHeight: 20 },
  confirmActions: { marginTop: 14, flexDirection: 'row', justifyContent: 'flex-end', alignItems: 'center', gap: 18 },
  cancel: { color: colors.muted, fontWeight: '800' },
  confirmButton: { backgroundColor: colors.danger, borderRadius: 10, minHeight: 40, minWidth: 96, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 14 },
  confirmButtonText: { color: '#FFF', fontWeight: '900' },
});
