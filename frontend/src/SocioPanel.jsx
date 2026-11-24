import { useCallback, useEffect, useState } from 'react';
import './socio-panel.css';

const fechaHora = valor => new Date(valor).toLocaleString('es-CL', {
  timeZone: 'America/Santiago', dateStyle: 'medium', timeStyle: 'short',
});

const fechaCorta = valor => {
  if (!valor) return '—';
  const partes = valor.split('-');
  return partes.length === 3 ? `${partes[2]}/${partes[1]}/${partes[0]}` : valor;
};

function descripcionError(error, alternativa) {
  return error?.message || alternativa;
}

export default function SocioPanel({ token, perfil, api, alCambiarContrasena }) {
  const [vista, setVista] = useState('resumen');
  const [datos, setDatos] = useState(null);
  const [qr, setQr] = useState(null);
  const [qrFallido, setQrFallido] = useState(false);
  const [error, setError] = useState('');
  const [aviso, setAviso] = useState('');
  const [ocupado, setOcupado] = useState(false);
  const [recarga, setRecarga] = useState(0);
  const [formulario, setFormulario] = useState({ first_name: '', last_name: '', email: '' });
  const [contrasena, setContrasena] = useState({ old_password: '', new_password1: '', new_password2: '' });
  const [cargandoPerfil, setCargandoPerfil] = useState(false);
  const [errorPerfil, setErrorPerfil] = useState('');

  const actualizar = useCallback(() => setRecarga(valor => valor + 1), []);

  useEffect(() => {
    let activo = true;
    let objetoQr = null;
    async function cargar() {
      setError('');
      try {
        const [clases, reservas] = await Promise.all([
          api('clases/', { token }),
          api('reservas/', { token }),
        ]);
        let membresia = null;
        try {
          membresia = await api('mi-membresia/', { token });
        } catch (fallo) {
          if (fallo.status !== 404) throw fallo;
        }
        if (!activo) return;
        setDatos({ clases, reservas, membresia });
        setQr(null);
        setQrFallido(false);
        if (membresia) {
          try {
            const blob = await api('mi-qr/', { token, respuesta: 'blob' });
            if (activo) {
              objetoQr = URL.createObjectURL(blob);
              setQr(objetoQr);
            }
          } catch {
            if (activo) {
              setQrFallido(true);
              setError('No se pudo cargar el código QR. Puedes usar el código de texto.');
            }
          }
        }
      } catch (fallo) {
        if (activo) setError(descripcionError(fallo, 'No se pudo cargar la información.'));
      }
    }
    cargar();
    return () => {
      activo = false;
      if (objetoQr) URL.revokeObjectURL(objetoQr);
    };
  }, [api, token, recarga]);

  useEffect(() => {
    if (vista !== 'perfil') return undefined;
    let activo = true;
    setCargandoPerfil(true);
    setErrorPerfil('');
    api('mi-cuenta/', { token })
      .then(cuenta => {
        if (activo) setFormulario({
          first_name: cuenta.first_name ?? cuenta.nombre ?? '',
          last_name: cuenta.last_name ?? '',
          email: cuenta.email ?? '',
        });
      })
      .catch(fallo => {
        if (activo) setErrorPerfil(descripcionError(fallo, 'No se pudo cargar el perfil.'));
      })
      .finally(() => { if (activo) setCargandoPerfil(false); });
    return () => { activo = false; };
  }, [api, token, vista]);

  async function realizar(ruta, contenido, texto) {
    setOcupado(true);
    setAviso('');
    setError('');
    try {
      await api(ruta, {
        token,
        method: 'POST',
        ...(contenido ? { body: JSON.stringify(contenido) } : {}),
      });
      setAviso(texto);
      actualizar();
    } catch (fallo) {
      setError(descripcionError(fallo, 'No se pudo completar la operación.'));
    } finally {
      setOcupado(false);
    }
  }

  async function guardarPerfil(evento) {
    evento.preventDefault();
    setOcupado(true);
    setAviso('');
    setErrorPerfil('');
    try {
      await api('mi-cuenta/', { token, method: 'PATCH', body: JSON.stringify(formulario) });
      setAviso('Tus datos se actualizaron correctamente.');
    } catch (fallo) {
      setErrorPerfil(descripcionError(fallo, 'No se pudieron guardar los datos.'));
    } finally {
      setOcupado(false);
    }
  }

  async function guardarContrasena(evento) {
    evento.preventDefault();
    setOcupado(true);
    setAviso('');
    setErrorPerfil('');
    try {
      await api('mi-cuenta/contrasena/', { token, method: 'POST', body: JSON.stringify(contrasena) });
      setContrasena({ old_password: '', new_password1: '', new_password2: '' });
      alCambiarContrasena();
    } catch (fallo) {
      setErrorPerfil(descripcionError(fallo, 'No se pudo cambiar la contraseña.'));
    } finally {
      setOcupado(false);
    }
  }

  const clases = datos?.clases ?? [];
  const reservas = datos?.reservas ?? [];
  const clasesFuturas = clases.filter(clase => new Date(clase.inicio).getTime() > Date.now());
  const clasePorId = new Map(clases.map(clase => [clase.id, clase]));
  const reservasPorClase = new Map(reservas.map(reserva => [reserva.clase, reserva]));
  const nombre = formulario.first_name || perfil.first_name || perfil.nombre || perfil.usuario;

  return (
    <>
      <div className="encabezado">
        <div>
          <p className="eyebrow">MI CUENTA</p>
          <h1>Hola, {nombre}.</h1>
          <p>Tu membresía y tus próximas actividades, en un solo lugar.</p>
        </div>
      </div>
      <nav className="socio-vistas" aria-label="Secciones de mi cuenta">
        <button type="button" className={vista === 'resumen' ? 'socio-vista-activa' : ''} aria-current={vista === 'resumen' ? 'page' : undefined} onClick={() => { setVista('resumen'); setAviso(''); setErrorPerfil(''); }}>Resumen</button>
        <button type="button" className={vista === 'perfil' ? 'socio-vista-activa' : ''} aria-current={vista === 'perfil' ? 'page' : undefined} onClick={() => { setVista('perfil'); setAviso(''); setErrorPerfil(''); }}>Mis datos</button>
        <button type="button" className={vista === 'contrasena' ? 'socio-vista-activa' : ''} aria-current={vista === 'contrasena' ? 'page' : undefined} onClick={() => { setVista('contrasena'); setAviso(''); setErrorPerfil(''); }}>Cambiar contraseña</button>
      </nav>
      {aviso && <div className="mensaje" role="status">{aviso}</div>}
      {vista === 'contrasena' ? (
        <section className="panel socio-perfil">
          <div className="panel-titulo"><div><p className="eyebrow">MI CUENTA</p><h2>Cambiar contraseña</h2></div></div>
          {errorPerfil && <div className="mensaje error" role="alert">{errorPerfil}</div>}
          <form onSubmit={guardarContrasena}>
            <label htmlFor="clave-actual">Contraseña actual</label>
            <input id="clave-actual" type="password" autoComplete="current-password" required value={contrasena.old_password} onChange={e => setContrasena({ ...contrasena, old_password: e.target.value })} />
            <label htmlFor="clave-nueva">Nueva contraseña</label>
            <input id="clave-nueva" type="password" autoComplete="new-password" required value={contrasena.new_password1} onChange={e => setContrasena({ ...contrasena, new_password1: e.target.value })} />
            <label htmlFor="clave-confirmacion">Confirmar nueva contraseña</label>
            <input id="clave-confirmacion" type="password" autoComplete="new-password" required value={contrasena.new_password2} onChange={e => setContrasena({ ...contrasena, new_password2: e.target.value })} />
            <button disabled={ocupado} type="submit">Cambiar contraseña</button>
          </form>
        </section>
      ) : vista === 'perfil' ? (
        <section className="panel socio-perfil">
          <div className="panel-titulo"><div><p className="eyebrow">MI CUENTA</p><h2>Mis datos</h2></div></div>
          {errorPerfil && <div className="mensaje error" role="alert">{errorPerfil}</div>}
          {cargandoPerfil ? <p>Cargando datos…</p> : !errorPerfil && (
            <form onSubmit={guardarPerfil}>
              <label htmlFor="socio-nombre">Nombre</label>
              <input id="socio-nombre" value={formulario.first_name} onChange={e => setFormulario({ ...formulario, first_name: e.target.value })} maxLength={150} />
              <label htmlFor="socio-apellidos">Apellidos</label>
              <input id="socio-apellidos" value={formulario.last_name} onChange={e => setFormulario({ ...formulario, last_name: e.target.value })} maxLength={150} />
              <label htmlFor="socio-email">Correo electrónico</label>
              <input id="socio-email" type="email" value={formulario.email} onChange={e => setFormulario({ ...formulario, email: e.target.value })} maxLength={254} />
              <button disabled={ocupado} type="submit">Guardar cambios</button>
            </form>
          )}
        </section>
      ) : (
        <>
          {error && <div className="mensaje error" role="alert">{error}</div>}
          {!datos ? (
            error ? <button type="button" onClick={actualizar}>Reintentar</button> : <p>Cargando tu información…</p>
          ) : (
            <>
              <div className="paneles">
                <section className="panel membresia">
                  <div className="panel-titulo"><div><p className="eyebrow">MI PLAN</p><h2>Tu membresía</h2></div></div>
                  {datos.membresia ? (
                    <>
                      <div className="plan-nombre">
                        {datos.membresia.plan_nombre || `Plan ${datos.membresia.plan}`}
                        <span className={`estado ${datos.membresia.vigente ? 'estado-ok' : 'estado-error'}`}>{datos.membresia.estado_visible}</span>
                      </div>
                      <p>Vigencia: {fechaCorta(datos.membresia.inicio)} al {fechaCorta(datos.membresia.fin)}</p>
                      {!datos.membresia.vigente && <p>Actualmente no está vigente.</p>}
                      <div className="qr">
                        {qr ? <img width="140" height="140" src={qr} alt="Código QR personal" /> : <span className="socio-qr-espera">{qrFallido ? 'QR no disponible' : 'Cargando QR…'}</span>}
                        <div><b>Tu código de acceso</b><p>Preséntalo en recepción o utiliza el código para la simulación.</p><code>{datos.membresia.codigo}</code></div>
                      </div>
                    </>
                  ) : <div className="vacio"><b>Sin membresía registrada</b><p>Consulta en recepción para activar tu plan.</p></div>}
                </section>
                <section className="panel">
                  <div className="panel-titulo"><div><p className="eyebrow">TU AGENDA</p><h2>Mis reservas</h2></div></div>
                  {reservas.length ? reservas.map(reserva => {
                    const clase = clasePorId.get(reserva.clase);
                    const puedeCancelar = clase && new Date(clase.inicio).getTime() > Date.now();
                    return <div className="fila" key={reserva.id}>
                      <div className="fila-detalle"><b>{clase ? clase.nombre : `Clase ${reserva.clase}`}</b>
                        <small>{clase && `${fechaHora(clase.inicio)} · `}{reserva.espera ? `Lista de espera${reserva.posicion ? ` · posición ${reserva.posicion}` : ''}` : 'Confirmada'}</small></div>
                      {puedeCancelar ? <button type="button" className="secundario" disabled={ocupado} onClick={() => realizar(`reservas/${reserva.id}/cancelar/`, null, 'Tu reserva fue cancelada.')}>Cancelar</button> : <span className="estado">Clase iniciada</span>}
                    </div>;
                  }) : <div className="vacio"><b>Aún no tienes reservas</b><p>Explora las próximas clases para comenzar.</p></div>}
                </section>
              </div>
              <section className="panel">
                <div className="panel-titulo"><div><p className="eyebrow">ENCUENTRA TU CLASE</p><h2>Próximas clases</h2></div></div>
                {clasesFuturas.length ? clasesFuturas.map(clase => {
                  const reserva = reservasPorClase.get(clase.id);
                  return <div className="fila" key={clase.id}>
                    <div className="fila-detalle"><b>{clase.nombre}</b><small>{fechaHora(clase.inicio)} · {clase.disponibles} disponibles de {clase.cupos} cupos</small></div>
                    {reserva ? <span className="estado estado-ok">{reserva.espera ? 'En espera' : 'Reservada'}</span> : <button type="button" disabled={ocupado} onClick={() => realizar('reservas/reservar/', { clase: clase.id }, clase.disponibles ? 'Reserva registrada.' : 'Inscripción en lista de espera registrada.')}>{clase.disponibles ? 'Reservar' : 'Unirse a espera'}</button>}
                  </div>;
                }) : <div className="vacio"><b>No hay clases próximas</b><p>Vuelve a consultar más adelante.</p></div>}
              </section>
            </>
          )}
        </>
      )}
    </>
  );
}
