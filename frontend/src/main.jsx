import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './estilos.css';
import AdminGestion from './AdminGestion';
import SocioPanel from './SocioPanel';
import DemoControles from './DemoControles';

let accesoActual = null;
let renovacion = null;
let renovacionPendiente = null;
let actualizarSesion = () => {};
let generacionSesion = 0;

async function api(ruta, { token, respuesta: formato, ...opciones } = {}) {
  const generacionPeticion = generacionSesion;
  const enviar = clave => fetch(`/api/${ruta}`, {
    ...opciones,
    headers: { ...(opciones.body ? { 'Content-Type': 'application/json' } : {}), ...(clave ? { Authorization: `Bearer ${clave}` } : {}), ...opciones.headers },
  });
  let respuesta = await enviar(token ? (accesoActual || token) : null);
  if (respuesta.status === 401 && token && renovacion && generacionPeticion === generacionSesion) {
    const generacionInicial = generacionSesion;
    if (!renovacionPendiente) {
      renovacionPendiente = fetch('/api/token/refresh/', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh: renovacion }),
      }).then(async r => {
        if (!r.ok) throw new Error('La sesión ha caducado.');
        return r.json();
      }).finally(() => { renovacionPendiente = null; });
    }
    try {
      const datos = await renovacionPendiente;
      if (generacionInicial !== generacionSesion) throw new Error('La sesión ha finalizado.');
      accesoActual = datos.access;
      actualizarSesion(datos.access);
      respuesta = await enviar(datos.access);
    } catch {
      if (generacionInicial === generacionSesion) {
        accesoActual = null; renovacion = null; actualizarSesion(null);
      }
      throw new Error('La sesión ha caducado. Vuelve a iniciar sesión.');
    }
  }
  if (respuesta.status === 401 && token && generacionPeticion === generacionSesion) {
    accesoActual = null; renovacion = null; actualizarSesion(null);
  }
  if (!respuesta.ok) {
    const detalle = await respuesta.json().catch(() => ({}));
    const mensajes = Object.entries(detalle).flatMap(([campo, valor]) =>
      (Array.isArray(valor) ? valor : [valor]).filter(x => typeof x === 'string').map(x => campo === 'detail' || campo === 'non_field_errors' ? x : `${campo}: ${x}`));
    const error = new Error(mensajes.join(' ') || 'No se pudo completar la operación.');
    error.status = respuesta.status;
    error.data = detalle;
    throw error;
  }
  if (respuesta.status === 204) return null;
  if (formato === 'blob') return respuesta.blob();
  return respuesta.json();
}

function Marca() {
  return <span className="marca"><span className="marca-icono">F<span>.</span></span><span>fitlife<small>CLUB DEPORTIVO</small></span></span>;
}

function Login({ entrar }) {
  const [usuario, setUsuario] = useState('');
  const [clave, setClave] = useState('');
  const [error, setError] = useState('');
  const [cargando, setCargando] = useState(false);
  async function enviar(evento) {
    evento.preventDefault(); setError(''); setCargando(true);
    try {
      const datos = await api('token/', { method: 'POST', body: JSON.stringify({ username: usuario, password: clave }) });
      const perfil = await api('mi-cuenta/', { token: datos.access });
      entrar(datos.access, perfil, datos.refresh);
    } catch { setError('No fue posible iniciar sesión. Revisa tus datos.'); }
    finally { setCargando(false); }
  }
  return <div className="acceso-pagina"><header className="acceso-cabecera"><span className="acceso-marca"><span className="acceso-marca-icono">F<span>.</span></span>fitlife</span><span className="acceso-cabecera-texto">Club deportivo</span></header><div className="acceso-centro"><section className="acceso-tarjeta"><div className="acceso-intro"><p className="acceso-etiqueta">ACCESO DE SOCIOS Y PERSONAL</p><h1>Iniciar sesión</h1><p>Ingresa con tu usuario y contraseña.</p></div>{error && <div className="acceso-error" role="alert">{error}</div>}<form className="acceso-formulario" onSubmit={enviar}><div className="acceso-campo"><label htmlFor="usuario">Nombre de usuario</label><input id="usuario" value={usuario} onChange={e => setUsuario(e.target.value)} autoComplete="username" required /></div><div className="acceso-campo"><label htmlFor="clave">Contraseña</label><input id="clave" type="password" value={clave} onChange={e => setClave(e.target.value)} autoComplete="current-password" required /></div><button disabled={cargando}>{cargando ? 'Ingresando…' : 'Ingresar'}</button></form><div className="acceso-ayuda"><strong>¿Aún no tienes una cuenta?</strong><p>Solicita tu registro en la recepción del gimnasio.</p></div></section></div><footer className="acceso-pie">FitLife · Control de asistencia y reservas</footer></div>;
}

const fecha = valor => new Date(valor).toLocaleString('es-CL', { timeZone: 'America/Santiago', dateStyle: 'medium', timeStyle: 'short' });

function Admin({ token }) {
  const [resumen, setResumen] = useState(null);
  const [error, setError] = useState('');
  const [recarga, setRecarga] = useState(0);
  useEffect(() => {
    let activo = true;
    let temporizador;
    async function cargar() {
      try { const resultado = await api('resumen/', { token }); if (activo) { setResumen(resultado); setError(''); } }
      catch { if (activo) setError('No se pudo actualizar el resumen.'); }
      finally { if (activo) temporizador = setTimeout(cargar, 2000); }
    }
    cargar();
    return () => { activo = false; clearTimeout(temporizador); };
  }, [token, recarga]);
  return <><div className="encabezado encabezado-club"><div><p className="eyebrow">FITLIFE / EL CLUB EN MARCHA</p><h1>Hoy en<br /><em>FitLife.</em></h1><p>La actividad del gimnasio, de un vistazo.</p></div></div><DemoControles token={token} api={api} onCambio={() => setRecarga(valor => valor + 1)} /><div className="franja"><span>EL CLUB EN CIFRAS</span><span>Actualización automática</span></div>{error && <div className="mensaje error" role="alert">{error}</div>}{!resumen ? <p>Cargando resumen…</p> : <><div className="metricas"><section className="metrica destacado"><div className="metrica-top"><span>En el gimnasio</span></div><strong>{resumen.aforo}</strong><small>Aforo actual</small></section><section className="metrica"><div className="metrica-top"><span>Socios registrados</span></div><strong>{resumen.socios}</strong></section><section className="metrica"><div className="metrica-top"><span>Pagos registrados</span></div><strong>{resumen.pagos}</strong></section></div><div className="paneles"><section className="panel"><div className="panel-titulo"><h2>Próximas clases</h2></div>{resumen.clases.length ? resumen.clases.map(c => <div className="fila" key={c.id}><div className="fila-detalle"><b>{c.nombre}</b><small>{fecha(c.inicio)} · {c.disponibles} disponibles</small></div></div>) : <div className="vacio">No hay clases programadas.</div>}</section><section className="panel"><div className="panel-titulo"><h2>Últimos movimientos</h2></div>{resumen.accesos.length ? resumen.accesos.map((a,i) => <div className="fila" key={i}><div className="fila-detalle"><b>{a.socio}</b><small>{a.tipo} · {fecha(a.fecha)}</small></div><span className={a.permitido ? 'estado estado-ok' : 'estado estado-error'}>{a.permitido ? 'Permitido' : 'Rechazado'}</span></div>) : <div className="vacio">Aún no hay movimientos.</div>}</section></div></>}</>;
}

function App() {
  const [sesion, setSesion] = useState(null);
  const [seccion, setSeccion] = useState('resumen');
  useEffect(() => {
    actualizarSesion = token => setSesion(actual => token && actual ? { ...actual, token } : null);
    return () => { actualizarSesion = () => {}; };
  }, []);

  function iniciar(token, perfil, refresh) {
    generacionSesion += 1;
    accesoActual = token;
    renovacion = refresh;
    setSesion({ token, perfil });
    setSeccion('resumen');
  }

  function salir() {
    generacionSesion += 1;
    accesoActual = null;
    renovacion = null;
    setSesion(null);
  }

  if (!sesion) return <Login entrar={iniciar} />;
  const opciones = [
    ['resumen', 'Resumen'], ['socios', 'Socios'], ['membresias', 'Membresías'],
    ['planes', 'Planes'], ['pagos', 'Pagos'], ['clases', 'Clases'],
    ['reservas', 'Reservas'], ['acceso', 'Control de acceso'],
  ];
  return (
    <div className="app">
      <aside className="sidebar">
        <Marca />
        {sesion.perfil.administrador && <nav aria-label="Navegación principal">
          {opciones.map(([valor, nombre]) => <button type="button" className="nav-boton" aria-current={seccion === valor ? 'page' : undefined} onClick={() => setSeccion(valor)} key={valor}>{nombre}</button>)}
        </nav>}
        <div className="sidebar-pie">
          <span className="usuario"><b>{sesion.perfil.nombre || sesion.perfil.usuario}</b><small>{sesion.perfil.administrador ? 'Administrador' : 'Socio'}</small></span>
          <button className="salir" onClick={salir}>Salir</button>
        </div>
      </aside>
      <div className="cuerpo">
        <header className="barra">FITLIFE / {sesion.perfil.administrador ? 'Administración' : 'Mi cuenta'}</header>
        <main className="contenido">
          {sesion.perfil.administrador
            ? seccion === 'resumen' ? <Admin token={sesion.token} /> : <AdminGestion token={sesion.token} seccion={seccion} api={api} />
            : <SocioPanel token={sesion.token} perfil={sesion.perfil} api={api} alCambiarContrasena={salir} />}
        </main>
      </div>
    </div>
  );
}

createRoot(document.getElementById('root')).render(<App />);
