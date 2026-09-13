import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Pressable, Text, View } from 'react-native';
import { api } from './api';
import { Button, Field, Notice } from './components';
import { colors } from './theme';
import { DAY_LABELS, DayPicker, EmptyState, InlineConfirm, ManagementShell, managementStyles as s, shortTime, Stat } from './managementComponents';

async function listOrEmpty(loader) {
  try {
    return await loader();
  } catch (error) {
    if (error.status === 404) return [];
    throw error;
  }
}

export function ClassesScreen({ onBack, onCreate, onOpen }) {
  const [classes, setClasses] = useState([]);
  const [day, setDay] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      setClasses(await listOrEmpty(() => api.listClasses()));
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const visible = day ? classes.filter((item) => item.dia_da_semana === day) : classes;

  return (
    <ManagementShell
      title="Agenda semanal"
      subtitle={`${classes.length} ${classes.length === 1 ? 'aula fixa' : 'aulas fixas'}`}
      onBack={onBack}
      refreshing={loading}
      action={<Pressable onPress={onCreate}><Text style={s.link}>＋ Nova aula</Text></Pressable>}
    >
      {error ? <Notice type="error">{error}</Notice> : null}
      <DayPicker value={day} onChange={setDay} allowAll />
      <View style={{ height: 18 }} />
      {!visible.length ? (
        <EmptyState
          title={classes.length ? 'Nenhuma aula nesse dia' : 'Sua agenda está vazia'}
          text={classes.length ? 'Escolha outro dia para visualizar sua agenda.' : 'Cadastre seus horários fixos e depois adicione os participantes.'}
          action={!classes.length ? <Button title="Cadastrar primeira aula" onPress={onCreate} /> : null}
        />
      ) : (
        <View style={s.cards}>
          {visible.map((item) => (
            <Pressable key={item.id} onPress={() => onOpen(item)} style={({ pressed }) => [s.card, pressed && s.cardPressed]}>
              <View style={s.cardTop}>
                <View style={s.grow}>
                  <Text style={s.cardTitle}>{DAY_LABELS[item.dia_da_semana]}</Text>
                  <Text style={s.cardText}>{shortTime(item.horario_inicio)} – {shortTime(item.horario_fim)}</Text>
                </View>
                <View style={s.badge}><Text style={s.badgeText}>ATÉ {item.quantidade_max_de_alunos}</Text></View>
              </View>
            </Pressable>
          ))}
        </View>
      )}
    </ManagementShell>
  );
}

export function ClassFormScreen({ classItem, onBack, onSaved }) {
  const editing = Boolean(classItem?.id);
  const [form, setForm] = useState({
    dia_da_semana: classItem?.dia_da_semana || 'segunda',
    horario_inicio: shortTime(classItem?.horario_inicio) || '08:00',
    horario_fim: shortTime(classItem?.horario_fim) || '09:00',
    capacidade_max: String(classItem?.quantidade_max_de_alunos || classItem?.capacidade_max || 1),
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const set = (key) => (value) => setForm((current) => ({ ...current, [key]: value }));

  const submit = async () => {
    const validTime = /^([01]\d|2[0-3]):[0-5]\d$/;
    if (!validTime.test(form.horario_inicio) || !validTime.test(form.horario_fim)) return setError('Use horários no formato HH:MM, por exemplo 08:30.');
    if (form.horario_fim <= form.horario_inicio) return setError('O horário final deve ser posterior ao inicial.');
    const capacidade = Number(form.capacidade_max);
    if (!Number.isInteger(capacidade) || capacidade < 1) return setError('A capacidade deve ser um número inteiro maior que zero.');

    const payload = {
      dia_da_semana: form.dia_da_semana,
      horario_inicio: form.horario_inicio,
      horario_fim: form.horario_fim,
      capacidade_max: capacidade,
    };

    setBusy(true);
    setError('');
    try {
      if (editing) await api.updateClass(classItem.id, payload);
      else await api.createClass(payload);
      onSaved();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <ManagementShell title={editing ? 'Editar aula' : 'Nova aula'} subtitle="Defina o dia, o período e a capacidade da turma." onBack={onBack}>
      {error ? <Notice type="error">{error}</Notice> : null}
      <View style={s.card}>
        <Text style={[s.meta, { marginBottom: 10 }]}>DIA DA SEMANA</Text>
        <DayPicker value={form.dia_da_semana} onChange={set('dia_da_semana')} />
        <View style={[s.twoColumns, { marginTop: 20 }]}>
          <View style={s.half}><Field label="Início" value={form.horario_inicio} onChangeText={set('horario_inicio')} placeholder="08:00" keyboardType="numbers-and-punctuation" maxLength={5} /></View>
          <View style={s.half}><Field label="Fim" value={form.horario_fim} onChangeText={set('horario_fim')} placeholder="09:00" keyboardType="numbers-and-punctuation" maxLength={5} /></View>
        </View>
        <Field label="Capacidade máxima" value={form.capacidade_max} onChangeText={set('capacidade_max')} keyboardType="number-pad" style={{ marginTop: 16 }} />
        <Text style={s.helper}>A capacidade não poderá ficar abaixo do número de alunos já matriculados.</Text>
        <Button title={editing ? 'Salvar alterações' : 'Cadastrar aula'} onPress={submit} loading={busy} style={{ marginTop: 22 }} />
      </View>
    </ManagementShell>
  );
}

export function ClassDetailScreen({ classItem: initialClass, onBack, onEdit, onDeleted, onOpenStudent }) {
  const [classItem, setClassItem] = useState(initialClass);
  const [participants, setParticipants] = useState([]);
  const [students, setStudents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [workingId, setWorkingId] = useState(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [allClasses, enrolled, allStudents] = await Promise.all([
        listOrEmpty(() => api.listClasses()),
        listOrEmpty(() => api.getClassStudents(initialClass.id)),
        api.listStudents(),
      ]);
      const current = allClasses.find((item) => item.id === initialClass.id);
      if (current) setClassItem(current);
      setParticipants(enrolled);
      setStudents(allStudents);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }, [initialClass.id]);

  useEffect(() => { load(); }, [load]);

  const participantIds = useMemo(() => new Set(participants.map((item) => item.aluno_id)), [participants]);
  const available = students.filter((student) => !participantIds.has(student.id));
  const capacity = classItem.quantidade_max_de_alunos || classItem.capacidade_max || 0;
  const full = capacity > 0 && participants.length >= capacity;

  const add = async (student) => {
    setWorkingId(student.id);
    setError('');
    setNotice('');
    try {
      const response = await api.addStudentToClass(student.id, classItem.id);
      setNotice(response.message);
      await load();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setWorkingId(null);
    }
  };

  const remove = async (student) => {
    setWorkingId(student.aluno_id);
    setError('');
    setNotice('');
    try {
      const response = await api.removeStudentFromClass(student.aluno_id, classItem.id);
      setNotice(response.message);
      await load();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setWorkingId(null);
    }
  };

  const deleteClass = async () => {
    setDeleting(true);
    setError('');
    try {
      await api.deleteClass(classItem.id);
      onDeleted();
    } catch (requestError) {
      setError(requestError.message);
      setDeleting(false);
      setConfirmDelete(false);
    }
  };

  return (
    <ManagementShell
      title={DAY_LABELS[classItem.dia_da_semana] || 'Aula'}
      subtitle={`${shortTime(classItem.horario_inicio)} – ${shortTime(classItem.horario_fim)}`}
      onBack={onBack}
      refreshing={loading}
      action={<Pressable onPress={() => onEdit(classItem)}><Text style={s.link}>Editar</Text></Pressable>}
    >
      {error ? <Notice type="error">{error}</Notice> : null}
      {notice ? <Notice>{notice}</Notice> : null}
      <View style={s.row}>
        <Stat value={participants.length} label="matriculados" />
        <Stat value={capacity || '—'} label="capacidade" />
        <Stat value={Math.max(capacity - participants.length, 0)} label="vagas" />
      </View>

      <Text style={s.sectionTitle}>Participantes</Text>
      {!participants.length ? <EmptyState title="Turma vazia" text="Escolha um aluno abaixo para iniciar esta turma." /> : (
        <View style={s.cards}>
          {participants.map((student) => (
            <View key={student.aluno_id} style={s.participant}>
              <Pressable style={s.participantInfo} onPress={() => onOpenStudent({ id: student.aluno_id, nome: student.nome_aluno, telefone: student.telefone })}>
                <Text style={s.participantName}>{student.nome_aluno}</Text>
                <Text style={s.participantPhone}>{student.telefone}</Text>
              </Pressable>
              <Pressable disabled={workingId === student.aluno_id} onPress={() => remove(student)}>
                <Text style={s.dangerLink}>{workingId === student.aluno_id ? 'Removendo…' : 'Remover'}</Text>
              </Pressable>
            </View>
          ))}
        </View>
      )}

      <Text style={s.sectionTitle}>Adicionar aluno</Text>
      {full ? <Notice type="error">A turma atingiu a capacidade máxima. Aumente a capacidade para adicionar outro aluno.</Notice> : null}
      {!students.length ? <EmptyState title="Nenhum aluno cadastrado" text="Cadastre alunos antes de montar a turma." /> : !available.length ? <EmptyState title="Todos já estão na turma" text="Não há outros alunos disponíveis para matrícula." /> : (
        <View style={s.cards}>
          {available.map((student) => (
            <View key={student.id} style={s.participant}>
              <View style={s.participantInfo}><Text style={s.participantName}>{student.nome}</Text><Text style={s.participantPhone}>{student.telefone}</Text></View>
              <Pressable disabled={full || workingId === student.id} onPress={() => add(student)}>
                <Text style={[s.link, full && { color: colors.muted }]}>{workingId === student.id ? 'Adicionando…' : 'Adicionar'}</Text>
              </Pressable>
            </View>
          ))}
        </View>
      )}

      <Text style={s.sectionTitle}>Zona de risco</Text>
      <View style={s.card}>
        <Text style={s.cardTitle}>Excluir aula</Text>
        <Text style={s.cardText}>A aula e suas matrículas serão removidas. Os alunos continuarão cadastrados.</Text>
        {!confirmDelete ? <Button title="Excluir aula" variant="danger" onPress={() => setConfirmDelete(true)} /> : <InlineConfirm text="Excluir esta aula fixa? Essa ação não pode ser desfeita." onCancel={() => setConfirmDelete(false)} onConfirm={deleteClass} loading={deleting} />}
      </View>
    </ManagementShell>
  );
}
