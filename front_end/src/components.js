import React from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { colors } from './theme';

export function Logo() {
  return <View style={styles.logo}><Text style={styles.logoMark}>T</Text></View>;
}

export function Field({ label, error, style, ...props }) {
  return (
    <View style={style}>
      <Text style={styles.label}>{label}</Text>
      <TextInput placeholderTextColor="#98A19C" style={[styles.input, error && styles.inputError]} {...props} />
      {error ? <Text style={styles.error}>{error}</Text> : null}
    </View>
  );
}

export function Button({ title, onPress, loading, variant = 'primary', disabled, style }) {
  return (
    <Pressable disabled={disabled || loading} onPress={onPress} style={({ pressed }) => [styles.button, styles[`${variant}Button`], (pressed || disabled) && styles.dim, style]}>
      {loading ? <ActivityIndicator color={variant === 'primary' ? colors.ink : colors.primaryDark} /> : <Text style={[styles.buttonText, styles[`${variant}Text`]]}>{title}</Text>}
    </Pressable>
  );
}

export function Notice({ type = 'success', children }) {
  return <View style={[styles.notice, type === 'error' ? styles.noticeError : styles.noticeSuccess]}><Text style={styles.noticeText}>{children}</Text></View>;
}

const styles = StyleSheet.create({
  logo: { width: 48, height: 48, borderRadius: 15, backgroundColor: colors.ink, alignItems: 'center', justifyContent: 'center' },
  logoMark: { color: colors.primary, fontSize: 27, fontWeight: '900', fontStyle: 'italic' },
  label: { color: colors.ink, fontSize: 14, fontWeight: '700', marginBottom: 7 },
  input: { height: 54, borderWidth: 1, borderColor: colors.line, backgroundColor: colors.surface, borderRadius: 14, paddingHorizontal: 16, color: colors.ink, fontSize: 16 },
  inputError: { borderColor: colors.danger },
  error: { color: colors.danger, fontSize: 12, marginTop: 5 },
  button: { minHeight: 54, borderRadius: 14, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 18 },
  primaryButton: { backgroundColor: colors.primary },
  secondaryButton: { backgroundColor: 'transparent', borderColor: colors.line, borderWidth: 1 },
  dangerButton: { backgroundColor: colors.dangerSoft, borderColor: '#F0CACA', borderWidth: 1 },
  buttonText: { fontSize: 16, fontWeight: '800' },
  primaryText: { color: colors.ink }, secondaryText: { color: colors.ink }, dangerText: { color: colors.danger },
  dim: { opacity: 0.55 },
  notice: { padding: 14, borderRadius: 12, marginBottom: 16 },
  noticeSuccess: { backgroundColor: colors.successSoft }, noticeError: { backgroundColor: colors.dangerSoft },
  noticeText: { color: colors.ink, lineHeight: 20 },
});
