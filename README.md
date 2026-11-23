# smartcut

`smartcut` adalah program Python untuk memotong video dengan metode smartcut. 

## Persyaratan

- [Python 3.10](https://www.python.org/downloads/) atau lebih baru
- [FFmpeg](https://ffmpeg.org/) (termasuk `ffprobe`)

## Instalasi

```bash
sudo apt update
sudo apt install -y python3 python3-venv ffmpeg git
git clone https://github.com/hyunazmi/smartcut.git
cd smartcut
python3 -m venv .venv
source .venv/bin/activate
pip install .
```

Verifikasi:

```bash
smartcut --version
```

> [!NOTE]
> Setiap membuka terminal baru, aktifkan dulu venv-nya sebelum menjalankan smartcut:

```bash
cd smartcut
source .venv/bin/activate
```

## Penggunaan

smartcut memiliki 2 mode: mode interaktif dan mode CLI.

### Mode Interaktif

```bash
smartcut
```

### Mode CLI

Dasar:

```bash
smartcut -f <file> -s <waktu_awal> -e <waktu_akhir>
```

Menentukan file output:

```bash
smartcut -f <file> -s <waktu_awal> -e <waktu_akhir> -o <output>
```

Mengaktifkan mode verbose:

```bash
smartcut -f <file> -s <waktu_awal> -e <waktu_akhir> -v
```

Menggunakan preset dan CRF tertentu:

```bash
smartcut -f <file> -s <waktu_awal> -e <waktu_akhir> -p medium -c 24
```

Contoh:

```bash
smartcut -f video.mp4 -s 00:01:30 -e 00:02:45
```

## Lisensi

[MIT](LICENSE)
