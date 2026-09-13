import React, { useCallback, useEffect, useState } from 'react';
import { Pressable, Text, View } from 'react-native';
import { api } from './api';
import { Button, Field, Notice } from './components';
import { colors } from './theme';
import { DAY_LABELS, EmptyState, InlineConfirm, ManagementShell, managementStyles as s, shortTime, Stat } from './managementComponents';

export function StudentsScreen({ onBack, onCreate, onOpen }) {
  const [students, setStudents] = useState([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      setStudents(await api.listStudents());
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const normalized = search.trim().toLocaleLowerCase('pt-BR');
  const visible = students.filter((student) => !normalized
    || student.nome.toLocaleLowerCase('pt-BR').includes(normalized)
    || student.telefone.includes(normalized));

  return (
    <ManagementShell
      title="Alunos"
      subtitle={`${students.length} ${students.length === 1 ? 'aluno cadastrado' : 'alunos cadastrados'}`}
      onBack={onBack}
      refreshing={loading}
      action={<Pressable onPress={onCreate}><Text style={s.link}>＋ Novo aluno</Text></Pressable>}
    >
      {error ? <Notice type="error">{error}</Notice> : null}
      <View style={s.toolbar}>
        <View style={s.grow}><Field label="Buscar" value={search} onChangeText={setSearch} placeholder="Nome ou telefone" /></View>
      </View>
      {!visible.length ? (
        <EmptyState
          title={students.length ? 'Nenhum resultado' : 'Sua lista está vazia'}
          text={students.length ? 'Tente buscar por outro nome ou telefone.' : 'Cadastre o primeiro aluno para começar a organizar suas aulas.'}
          action={!students.length ? <Button title="Cadastrar aluno" onPress={onCreate} /> : null}
        />
      ) : (
        <View style={s.cards}>
          {visible.map((student) => (
            <Pressable key={student.id} onPress={() => onOpen(student)} style={({ pressed }) => [s.card, pressed && s.cardPressed]}>
              <View style={s.cardTop}>
                <View style={s.grow}>
                  <Text style={s.cardTitle}>{student.nome}</Text>
                  <Text style={s.cardText}>{student.telefone}</Text>
                </View>
                <Text style={{ color: colors.muted, fontSize: 28 }}>›</Text>
              </View>
            </Pressable>
          ))}
        </View>
      )}
    </ManagementShell>
  );
}

export function StudentFormScreen({ student, onBack, onSaved }) {
  const editing = Boolean(student?.id);
  const [form, setForm] = useState({ nome: student?.nome || '', telefone: student?.telefone || '' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const set = (key) => (value) => setForm((current) => ({ ...current, [key]: value }));

  const submit = async () => {
    const nome = form.nome.trim();
    const telefone = form.telefone.trim();
    if (!nome || !telefone) return setError('Preencha o nome e o telefone.');
    setBusy(true);
    setError('');
    try {
      if (editing) await api.updateStudent(student.id, { nome, telefone });
      else await api.createStudent({ nome, telefone });
      onSaved();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <ManagementShell title={editing ? 'Editar aluno' : 'Novo aluno'} subtitle={editing ? 'Atualize os dados de contato.' : 'Adicione um aluno à sua carteira.'} onBack={onBack}>
      {error ? <Notice type="error">{error}</Notice> : null}
      <View style={s.card}>
        <Field label="Nome completo" value={form.nome} onChangeText={set('nome')} placeholder="Nome do aluno" />
        <Field label="Telefone" value={form.telefone} onChangeText={set('telefone')} placeholder="(85) 99999-9999" keyboardType="phone-pad" style={{ marginTop: 16 }} />
        <Button title={editing ? 'Salvar alterações' : 'Cadastrar aluno'} onPress={submit} loading={busy} style={{ marginTop: 22 }} />
      </View>
    </ManagementShell>
  );
}

export function StudentDetailScreen({ student: initialStudent, onBack, onEdit, onDeleted, onOpenClass }) {
  const [student, setStudent] = useState(initialStudent);
  const [classes, setClasses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const currentStudent = await api.getStudent(initialStudent.id);
      setStudent(currentStudent);
      try {
        setClasses(await api.getStudentClasses(initialStudent.id));
      } catch (requestError) {
        if (requestError.status === 404) setClasses([]);
        else throw requestError;
      }
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }, [initialStudent.id]);

  useEffect(() => { load(); }, [load]);

  const remove = async () => {
    setDeleting(true);
    setError('');
    try {
      await api.deleteStudent(student.id);
      onDeleted();
    } catch (requestError) {
      setError(requestError.message);
      setDeleting(false);
      setConfirmDelete(false);
    }
  };

  return (
    <ManagementShell title={student.nome} subtitle={student.telefone} onBack={onBack} refreshing={loading} action={<Pressable onPress={() => onEdit(student)}><Text style={s.link}>Editar</Text></Pressable>}>
      {error ? <Notice type="error">{error}</Notice> : null}
      <View style={s.row}>
        <Stat value={classes.length} label={classes.length === 1 ? 'aula semanal' : 'aulas semanais'} />
        <Stat value={`#${student.id}`} label="identificador" />
      </View>

      <Text style={s.sectionTitle}>Aulas deste aluno</Text>
      {!classes.length ? <EmptyState title="Nenhuma aula" text="Este aluno ainda não foi matriculado em uma aula fixa." /> : (
        <View style={s.cards}>
          {classes.map((item) => (
            <Pressable key={item.aula_id} onPress={() => onOpenClass({
              id: item.aula_id,
              dia_da_semana: item.dia_da_semana,
              horario_inicio: item.horario_inicio,
              horario_fim: item.horario_fim,
            })} style={({ pressed }) => [s.card, pressed && s.cardPressed]}>
              <View style={s.between}>
                <View><Text style={s.cardTitle}>{DAY_LABELS[item.dia_da_semana]}</Text><Text style={s.cardText}>{shortTime(item.horario_inicio)} – {shortTime(item.horario_fim)}</Text></View>
                <Text style={{ color: colors.muted, fontSize: 28 }}>›</Text>
              </View>
            </Pressable>
          ))}
        </View>
      )}

      <Text style={s.sectionTitle}>Zona de risco</Text>
      <View style={s.card}>
        <Text style={s.cardTitle}>Excluir aluno</Text>
        <Text style={s.cardText}>O aluno também será removido de todas as aulas em que estiver matriculado.</Text>
        {!confirmDelete ? <Button title="Excluir aluno" variant="danger" onPress={() => setConfirmDelete(true)} /> : <InlineConfirm text={`Excluir ${student.nome}? Essa ação não pode ser desfeita.`} onCancel={() => setConfirmDelete(false)} onConfirm={remove} loading={deleting} />}
      </View>
    </ManagementShell>
  );
}
