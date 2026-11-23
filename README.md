# snipy

`snipy` adalah program Python untuk memotong video dengan metode smart cut. 

## Persyaratan

- [Python 3.10](https://www.python.org/downloads/) atau lebih baru
- [FFmpeg](https://ffmpeg.org/) (termasuk `ffprobe`)

## Instalasi

```bash
sudo apt update
sudo apt install -y python3 python3-venv ffmpeg git
git clone https://github.com/hyunazmi/snipy.git
cd snipy
python3 -m venv .venv
source .venv/bin/activate
pip install .
```

Verifikasi:

```bash
snipy --version
```

> [!NOTE]
> Setiap membuka terminal baru, aktifkan dulu venv-nya sebelum menjalankan snipy:

```bash
cd snipy
source .venv/bin/activate
```

## Penggunaan

snipy memiliki 2 mode: mode interaktif dan mode CLI.

### Mode Interaktif

```bash
snipy
```

### Mode CLI

Dasar:

```bash
snipy -f <file> -s <waktu_awal> -e <waktu_akhir>
```

Menentukan file output:

```bash
snipy -f <file> -s <waktu_awal> -e <waktu_akhir> -o <output>
```

Mengaktifkan mode verbose:

```bash
snipy -f <file> -s <waktu_awal> -e <waktu_akhir> -v
```

Menggunakan preset dan CRF tertentu:

```bash
snipy -f <file> -s <waktu_awal> -e <waktu_akhir> -p medium -c 24
```

Contoh:

```bash
snipy -f video.mp4 -s 00:01:30 -e 00:02:45
```

## Lisensi

[MIT](LICENSE)
