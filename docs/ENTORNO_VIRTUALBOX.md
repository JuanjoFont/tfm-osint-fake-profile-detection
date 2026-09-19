# Reconstrucción del entorno evaluado

Este documento permite reconstruir el entorno de ejecución del TFM sin distribuir una imagen de máquina virtual, credenciales ni datos de terceros. La configuración registrada es **Oracle VM VirtualBox 7.2.10**, Ubuntu 25.04 (Plucky Puffin, 64 bits), 6 núcleos virtuales, 10.319 MB de memoria base, disco virtual de 25 GB y un adaptador de red en modo **NAT** con la opción **Cable conectado** habilitada.

## 1. Crear la máquina virtual

1. Instale Oracle VM VirtualBox 7.2.10 en el equipo anfitrión y descargue la imagen ISO oficial de Ubuntu 25.04 para arquitectura x86_64.
2. Cree una máquina nueva de tipo Linux/Ubuntu (64 bits). Asigne 6 CPU, 10.319 MB de RAM y un disco VDI dinámico de 25 GB.
3. En **Red**, mantenga habilitado el adaptador 1, seleccione **NAT** y active **Cable conectado**.
4. Monte la ISO e instale Ubuntu 25.04. Tras el primer arranque, retire la ISO virtual y aplique las actualizaciones del sistema.

La configuración NAT permite descargar dependencias y acceder a Zenodo sin exponer servicios de la máquina virtual en la red local. Si se requiere acceso entrante desde el anfitrión, debe documentarse una regla de redirección de puertos distinta; no formó parte de la configuración evaluada.

## 2. Preparar Ubuntu

Abra una terminal dentro de la máquina virtual y ejecute:

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip
git clone https://github.com/JuanjoFont/tfm-osint-fake-profile-detection.git
cd tfm-osint-fake-profile-detection
git checkout tfm-entorno-vbox-7.2.10
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

La etiqueta `tfm-entorno-vbox-7.2.10` identifica la versión pública que acompaña esta configuración. Si la etiqueta no aparece tras una clonación anterior, ejecute `git fetch --tags` antes de `git checkout`.

## 3. Verificar la reproducción sin datos externos

Con el entorno virtual activado, ejecute:

```bash
python scripts/verificar_manifest.py
python scripts/reproducir_sintetico.py --output salidas/reconstruccion_virtualbox
```

El primer comando debe informar de que el manifiesto es correcto. El segundo debe generar tres CSV en `salidas/reconstruccion_virtualbox/` y reproducir las métricas de referencia del benchmark sintético. Esta comprobación no descarga datos, no requiere credenciales y no reentrena el modelo de TwiBot-22.

## 4. Reproducir la ampliación Honduras/UAE

Descargue desde Zenodo los cuatro archivos originales indicados en [validacion_campanas/README.md](../validacion_campanas/README.md) y guárdelos en una carpeta local, fuera del repositorio. Después ejecute los comandos de preparación, experimentos, coordinación e informe que figuran en ese README, sustituyendo `/ruta/a/zenodo` por la ubicación real de los archivos.

Los datos crudos, los identificadores por cuenta, las particiones, las predicciones, los modelos serializados, las claves y los archivos `.env` no se incluyen en el repositorio público. Por ello, la reconstrucción pública permite verificar el código y los resultados agregados; repetir las campañas requiere obtener los originales bajo sus condiciones de uso.

## Evidencia de reconstrucción

La reconstrucción debe considerarse correcta cuando se cumplen estas comprobaciones:

- La máquina coincide con la configuración indicada en la sección 1.
- `python --version` informa Python 3.14.4, que es la versión registrada en el experimento.
- `python scripts/verificar_manifest.py` completa sin errores.
- `python scripts/reproducir_sintetico.py` genera las salidas esperadas.
- Con los archivos de Zenodo disponibles, `python validacion_campanas/verificar.py` termina con `status: passed`.

No se distribuye una OVA ni un snapshot. Esta guía constituye la alternativa reproducible solicitada: describe la versión del hipervisor, recursos, red, sistema operativo, dependencias, versión del código y comprobaciones de resultado.
