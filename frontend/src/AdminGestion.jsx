import React, { useEffect, useState } from 'react';
import './admin-gestion.css';

const recursos = {
  socios: {
    titulo: 'Socios', singular: 'socio',
    campos: [
      { nombre: 'username', etiqueta: 'Nombre de usuario', requerido: true },
      { nombre: 'first_name', etiqueta: 'Nombre' },
      { nombre: 'last_name', etiqueta: 'Apellidos' },
      { nombre: 'email', etiqueta: 'Correo electrónico', tipo: 'email' },
      { nombre: 'password', etiqueta: 'Contraseña', tipo: 'password', soloCreacionObligatoria: true },
      { nombre: 'is_active', etiqueta: 'Cuenta activa', tipo: 'checkbox', defecto: true },
    ],
    resumen: (item) => [nombreSocio(item), `${item.username} · ${item.email || 'Sin correo'} · ${item.is_active ? 'Activo' : 'Inactivo'}`],
  },
  planes: {
    titulo: 'Planes', singular: 'plan',
    campos: [
      { nombre: 'nombre', etiqueta: 'Nombre del plan', requerido: true },
      { nombre: 'precio', etiqueta: 'Precio', tipo: 'number', min: 0, requerido: true },
      { nombre: 'duracion_dias', etiqueta: 'Duración en días', tipo: 'number', min: 1, requerido: true },
    ],
    resumen: (item) => [item.nombre, `$${item.precio} · ${item.duracion_dias} días`],
  },
  membresias: {
    titulo: 'Membresías', singular: 'membresía', relaciones: ['socios', 'planes'],
    campos: [
      { nombre: 'socio', etiqueta: 'Socio', relacion: 'socios', requerido: true, bloqueadoEnEdicion: true },
      { nombre: 'plan', etiqueta: 'Plan', relacion: 'planes', requerido: true },
      { nombre: 'inicio', etiqueta: 'Inicio', tipo: 'date', requerido: true },
      { nombre: 'fin', etiqueta: 'Fin', tipo: 'date', requerido: true },
      { nombre: 'estado', etiqueta: 'Estado', opciones: [['activa', 'Activa'], ['vencida', 'Vencida'], ['congelada', 'Congelada']], defecto: 'activa', requerido: true },
    ],
    resumen: (item, listas) => [etiquetaRelacion('socios', item.socio, listas), `${etiquetaRelacion('planes', item.plan, listas)} · ${item.estado_visible} · ${item.inicio} al ${item.fin}`],
  },
  pagos: {
    titulo: 'Pagos', singular: 'pago', relaciones: ['membresias', 'socios'],
    campos: [
      { nombre: 'membresia', etiqueta: 'Membresía', relacion: 'membresias', requerido: true },
      { nombre: 'monto', etiqueta: 'Monto', tipo: 'number', min: 0, requerido: true },
      { nombre: 'fecha', etiqueta: 'Fecha', tipo: 'date', requerido: true },
      { nombre: 'detalle', etiqueta: 'Detalle' },
    ],
    resumen: (item, listas) => [`${etiquetaRelacion('membresias', item.membresia, listas)} · $${item.monto}`, `${item.fecha}${item.detalle ? ` · ${item.detalle}` : ''}`],
  },
  clases: {
    titulo: 'Clases', singular: 'clase',
    campos: [
      { nombre: 'nombre', etiqueta: 'Nombre de la clase', requerido: true },
      { nombre: 'inicio', etiqueta: 'Inicio (hora de Santiago)', tipo: 'datetime-local', requerido: true },
      { nombre: 'cupos', etiqueta: 'Cupos', tipo: 'number', min: 1, requerido: true },
    ],
    resumen: (item) => [item.nombre, `${fechaClase(item.inicio)} · ${item.cupos} cupos · ${item.disponibles} disponibles`],
  },
  reservas: {
    titulo: 'Reservas', singular: 'reserva', relaciones: ['socios', 'clases'],
    campos: [
      { nombre: 'socio', etiqueta: 'Socio', relacion: 'socios', requerido: true },
      { nombre: 'clase', etiqueta: 'Clase', relacion: 'clases', requerido: true },
    ],
    resumen: (item, listas) => [etiquetaRelacion('socios', item.socio, listas), `${etiquetaRelacion('clases', item.clase, listas)} · ${item.espera ? 'Lista de espera' : 'Confirmada'}`],
  },
};

function nombreSocio(socio) {
  return [socio.first_name, socio.last_name].filter(Boolean).join(' ') || socio.username;
}

function fechaClase(fecha) {
  if (!fecha) return '';
  const valor = new Date(fecha);
  return Number.isNaN(valor.getTime()) ? fecha : valor.toLocaleString('es-CL', { timeZone: 'America/Santiago', dateStyle: 'short', timeStyle: 'short' });
}

function fechaParaInput(fecha) {
  if (!fecha) return '';
  const valor = new Date(fecha);
  if (Number.isNaN(valor.getTime())) return fecha.slice(0, 16);
  const partes = Object.fromEntries(new Intl.DateTimeFormat('en-CA', {
    timeZone: 'America/Santiago', year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
  }).formatToParts(valor).map(({ type, value }) => [type, value]));
  return `${partes.year}-${partes.month}-${partes.day}T${partes.hour}:${partes.minute}`;
}

function etiquetaRelacion(tipo, id, listas) {
  const elemento = (listas[tipo] || []).find((item) => String(item.id) === String(id));
  if (!elemento) return `Registro ${id}`;
  if (tipo === 'socios') return `${nombreSocio(elemento)} (${elemento.username})`;
  if (tipo === 'clases') return `${elemento.nombre} · ${fechaClase(elemento.inicio)}`;
  if (tipo === 'membresias') return `${etiquetaRelacion('socios', elemento.socio, listas)} · ${elemento.estado_visible}`;
  return elemento.nombre;
}

function valoresIniciales(config, item) {
  return Object.fromEntries(config.campos.map((campo) => {
    let valor = item?.[campo.nombre] ?? campo.defecto ?? '';
    if (campo.tipo === 'datetime-local' && valor) valor = fechaParaInput(valor);
    return [campo.nombre, valor];
  }));
}

function erroresTexto(error) {
  if (error?.data && typeof error.data === 'object') {
    return Object.entries(error.data).map(([campo, detalle]) => `${campo === 'non_field_errors' ? 'Error' : campo}: ${Array.isArray(detalle) ? detalle.join(', ') : detalle}`).join(' · ');
  }
  return error?.message || 'No se pudo completar la operación.';
}

function ControlAcceso({ token, api }) {
  const [codigo, setCodigo] = useState('');
  const [tipo, setTipo] = useState('entrada');
  const [resultado, setResultado] = useState(null);
  const [ocupado, setOcupado] = useState(false);
  async function enviar(evento) {
    evento.preventDefault(); setOcupado(true); setResultado(null);
    try {
      const respuesta = await api('accesos/', { token, method: 'POST', body: JSON.stringify({ codigo: codigo.trim(), tipo }) });
      setResultado({ texto: respuesta.detalle, permitido: respuesta.permitido });
      if (respuesta.permitido) setCodigo('');
    } catch (error) { setResultado({ texto: erroresTexto(error), permitido: false }); }
    finally { setOcupado(false); }
  }
  return <><div className="encabezado"><div><p className="eyebrow">CONTROL DE ACCESO</p><h1>Registrar movimiento</h1><p>Ingresa el código del socio para simular la lectura QR.</p></div></div><section className="panel gestion-formulario"><form onSubmit={enviar}><label htmlFor="acceso-codigo">Código del socio</label><input id="acceso-codigo" value={codigo} onChange={(evento) => setCodigo(evento.target.value)} required /><label htmlFor="acceso-tipo">Movimiento</label><select id="acceso-tipo" value={tipo} onChange={(evento) => setTipo(evento.target.value)}><option value="entrada">Entrada</option><option value="salida">Salida</option></select><button disabled={ocupado}>{ocupado ? 'Validando…' : 'Validar movimiento'}</button></form>{resultado && <p className={resultado.permitido ? 'gestion-exito' : 'gestion-error'} role="status">{resultado.texto}</p>}</section></>;
}

export default function AdminGestion({ token, seccion, api }) {
  const [listas, setListas] = useState({});
  const [edicion, setEdicion] = useState(null);
  const [valores, setValores] = useState({});
  const [error, setError] = useState('');
  const [mensaje, setMensaje] = useState('');
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const config = recursos[seccion];

  async function cargar() {
    if (!config) return;
    setCargando(true); setError('');
    try {
      const nombres = [...new Set([seccion, ...(config.relaciones || [])])];
      const respuestas = await Promise.all(nombres.map((nombre) => api(`${nombre}/`, { token })));
      setListas(Object.fromEntries(nombres.map((nombre, indice) => [nombre, respuestas[indice]])));
    } catch (fallo) { setError(erroresTexto(fallo)); }
    finally { setCargando(false); }
  }

  useEffect(() => { setEdicion(null); setMensaje(''); setListas({}); cargar(); }, [seccion, token]);
  if (seccion === 'acceso') return <ControlAcceso token={token} api={api} />;
  if (!config) return <p>Sección no disponible.</p>;

  function abrir(item = null) {
    setValores(valoresIniciales(config, item)); setEdicion(item || { nuevo: true }); setError(''); setMensaje('');
  }

  async function guardar(evento) {
    evento.preventDefault(); setGuardando(true); setError('');
    const datos = { ...valores };
    if (seccion === 'socios' && !datos.password) delete datos.password;
    if (seccion === 'membresias' && !edicion.nuevo) delete datos.socio;
    try {
      await api(`${seccion}/${edicion.nuevo ? '' : `${edicion.id}/`}`, { token, method: edicion.nuevo ? 'POST' : 'PATCH', body: JSON.stringify(datos) });
      setEdicion(null); setMensaje('Los datos se guardaron correctamente.'); await cargar();
    } catch (fallo) { setError(erroresTexto(fallo)); }
    finally { setGuardando(false); }
  }

  async function eliminar(item) {
    const advertencia = seccion === 'clases' ? '¿Eliminar esta clase y todas sus reservas y lista de espera?' : `¿Eliminar este ${config.singular}?`;
    if (!window.confirm(advertencia)) return;
    setError(''); setMensaje('');
    try { await api(`${seccion}/${item.id}/`, { token, method: 'DELETE' }); setMensaje('El registro se eliminó correctamente.'); await cargar(); }
    catch (fallo) { setError(erroresTexto(fallo)); }
  }

  return <><div className="titulo"><div><p className="eyebrow">GESTIÓN / {config.titulo.toUpperCase()}</p><h1>{config.titulo}</h1></div><button onClick={() => abrir()}>Añadir {config.singular}</button></div>
    {mensaje && <div className="mensaje" role="status">{mensaje}</div>}
    {error && <div className="mensaje error" role="alert">{error}</div>}
    {edicion && <section className="panel gestion-formulario"><div className="panel-titulo"><h2>{edicion.nuevo ? 'Nuevo' : 'Editar'} {config.singular}</h2><button className="link" type="button" onClick={() => { setEdicion(null); setError(''); }}>Cerrar</button></div><form onSubmit={guardar}>
      {config.campos.map((campo) => <div className="gestion-campo" key={campo.nombre}>
        {campo.tipo === 'checkbox' ? <label className="gestion-checkbox"><input type="checkbox" checked={Boolean(valores[campo.nombre])} onChange={(evento) => setValores({ ...valores, [campo.nombre]: evento.target.checked })} />{campo.etiqueta}</label> : <><label htmlFor={`gestion-${campo.nombre}`}>{campo.etiqueta}</label>{campo.relacion || campo.opciones ? <select id={`gestion-${campo.nombre}`} value={valores[campo.nombre]} required={campo.requerido} disabled={campo.bloqueadoEnEdicion && !edicion.nuevo} onChange={(evento) => setValores({ ...valores, [campo.nombre]: evento.target.value })}><option value="">Selecciona una opción</option>{(campo.opciones || (listas[campo.relacion] || []).map((item) => [item.id, etiquetaRelacion(campo.relacion, item.id, listas)])).map(([valor, etiqueta]) => <option key={valor} value={valor}>{etiqueta}</option>)}</select> : <input id={`gestion-${campo.nombre}`} type={campo.tipo || 'text'} min={campo.min} value={valores[campo.nombre]} required={campo.requerido || (campo.soloCreacionObligatoria && edicion.nuevo)} onChange={(evento) => setValores({ ...valores, [campo.nombre]: evento.target.value })} />}{campo.nombre === 'password' && !edicion.nuevo && <small>Deja este campo vacío para conservar la contraseña.</small>}</>}
      </div>)}
      <div className="gestion-botones"><button type="submit" disabled={guardando}>{guardando ? 'Guardando…' : 'Guardar'}</button><button type="button" className="secundario" onClick={() => setEdicion(null)}>Cancelar</button></div>
    </form></section>}
    <section className="panel gestion-lista" aria-label={`Listado de ${config.titulo.toLowerCase()}`}>
      {cargando ? <p>Cargando registros…</p> : (listas[seccion] || []).length ? listas[seccion].map((item) => { const [titulo, detalle] = config.resumen(item, listas); return <div className="fila" key={item.id}><div className="fila-detalle"><b>{titulo}</b><small>{detalle}</small></div><div className="acciones"><button type="button" className="link" onClick={() => abrir(item)}>Editar</button><button type="button" className="link" onClick={() => eliminar(item)}>Eliminar</button></div></div>; }) : <div className="vacio"><b>No hay registros todavía.</b><p>Añade un {config.singular} para comenzar.</p></div>}
    </section>
  </>;
}
