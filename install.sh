#!/bin/bash

echo "🔍 환경 감지 중..."

OS_TYPE="$(uname)"
ARCH_TYPE="$(uname -m)"

echo "📦 기본 requirements.txt 설치 중..."
pip install -r requirements.txt

if [[ "$OS_TYPE" == "Darwin" ]]; then
  if [[ "$ARCH_TYPE" == "arm64" ]]; then
    echo "🍎 Mac (Apple Silicon) 환경 감지됨 - tensorflow-macos 설치 중..."
    pip install tensorflow-macos tensorflow-metal
  else
    echo "💻 Mac (Intel) 환경 감지됨 - tensorflow 설치 중..."
    pip install tensorflow
  fi
elif [[ "$OS_TYPE" == "Linux" ]]; then
  echo "🐧 Linux 환경 감지됨 - tensorflow 설치 중..."
  pip install tensorflow
elif [[ "$OS_TYPE" == "MINGW64_NT"* || "$OS_TYPE" == "CYGWIN"* || "$OS_TYPE" == "MSYS_NT"* ]]; then
  echo "🪟 Windows 환경 감지됨 - tensorflow 및 pywin32 설치 중..."
  pip install tensorflow pywin32
else
  echo "⚠️ 알 수 없는 환경입니다. 수동으로 tensorflow를 설치해주세요."
fi
