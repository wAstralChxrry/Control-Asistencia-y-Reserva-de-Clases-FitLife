import { useCallback, useEffect, useState } from 'react';
import './demo-controles.css';

/** Controles del lote de demostración del dashboard administrativo. */
export default function DemoControles({ token, api, onCambio }) {
  const [cargada, setCargada] = useState(null);
  const [consultando, setConsultando] = useState(true);
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState('');
  const [mensaje, setMensaje] = useState('');
  const [credenciales, setCredenciales] = useState(null);

  const consultar = useCallback(async () => {
    setConsultando(true);
    setError('');
    try {
      const estado = await api('demo/estado/', { token });
      setCargada(estado.cargada);
    } catch (fallo) {
      setCargada(null);
      setError(fallo.message || 'No se pudo consultar el estado de la demostración.');
    } finally {
      setConsultando(false);
    }
  }, [api, token]);

  useEffect(() => {
    consultar();
  }, [consultar]);

  async function ejecutar(accion) {
    if (accion === 'eliminar' && !window.confirm('¿Eliminar los datos creados para la demostración?')) return;
    setOcupado(true);
    setError('');
    setMensaje('');
    setCredenciales(null);
    try {
      const resultado = await api(`demo/${accion}/`, { token, method: 'POST' });
      if (accion === 'acceso') {
        setCredenciales({ usuario: resultado.usuario, clave: resultado.contrasena });
      } else {
        setCargada(resultado.cargada);
        setMensaje(resultado.detalle);
        if (onCambio) await onCambio();
      }
    } catch (fallo) {
      setError(fallo.message || 'No se pudo completar la operación.');
      await consultarEstadoTrasError();
    } finally {
      setOcupado(false);
    }
  }

  async function consultarEstadoTrasError() {
    try {
      const estado = await api('demo/estado/', { token });
      setCargada(estado.cargada);
    } catch {
      setCargada(null);
    }
  }

  return (
    <section className="panel demo-controles-react" aria-label="Datos de demostración">
      <div className="demo-controles-contenido">
        <div>
          <strong>Datos de demostración</strong>
          <p>
            {consultando
              ? 'Comprobando datos de demostración…'
              : cargada === null
              ? 'No se ha podido comprobar si hay datos de demostración.'
              : cargada
                ? 'Hay datos de ejemplo cargados.'
                : 'Carga socios, planes, clases y movimientos de ejemplo.'}
          </p>
        </div>
        <div className="demo-controles-acciones">
          {consultando ? null : cargada === null ? (
            <button type="button" disabled={ocupado} onClick={consultar}>Reintentar</button>
          ) : cargada ? (
            <>
              <button type="button" disabled={ocupado} onClick={() => ejecutar('acceso')}>Generar acceso de socio</button>
              <button type="button" className="demo-eliminar" disabled={ocupado} onClick={() => ejecutar('eliminar')}>Eliminar datos de prueba</button>
            </>
          ) : (
            <button type="button" disabled={ocupado} onClick={() => ejecutar('cargar')}>Cargar datos de prueba</button>
          )}
        </div>
      </div>
      {mensaje && <p className="demo-controles-aviso" role="status">{mensaje}</p>}
      {error && <p className="demo-controles-error" role="alert">{error}</p>}
      {credenciales && (
        <div className="demo-controles-credenciales" role="status">
          <strong>Acceso de demostración</strong>
          <p>Usuario: <code>{credenciales.usuario}</code></p>
          <p>Contraseña: <code>{credenciales.clave}</code></p>
        </div>
      )}
    </section>
  );
}
