#!/bin/bash
# E2E-Test der Integration in ephemerer HA (Port 8124, komplett getrennt).
# Erwartet: Kit unter /tmp/kit-upload, Treiber unter /tmp/int_test_driver.py
set -euo pipefail
TD=/tmp/int-test-config
rm -rf "$TD"; mkdir -p "$TD/custom_components"
cp -r /tmp/kit-upload/custom_components/garten_bewaesserung "$TD/custom_components/"

cat > "$TD/configuration.yaml" <<'EOF'
default_config:
homeassistant:
  name: IntTest
# Testbett: 3 Ventile + 2 Bodensensoren + Wetter — alles moderner template:-Key
input_boolean:
  v1: {name: V1}
  v2: {name: V2}
  v3: {name: V3}
input_number:
  flow:
    name: Flow
    min: 0
    max: 1000
    step: 0.001
template:
  - sensor:
      - name: testboden_1
        unit_of_measurement: "%"
        state: "42"
      - name: testboden_2
        unit_of_measurement: "%"
        state: "38"
      - name: testflow
        unit_of_measurement: "m³"
        state: "{{ states('input_number.flow') }}"
  - switch:
      - name: testventil_1
        state: "{{ is_state('input_boolean.v1','on') }}"
        turn_on: {action: input_boolean.turn_on, target: {entity_id: input_boolean.v1}}
        turn_off: {action: input_boolean.turn_off, target: {entity_id: input_boolean.v1}}
      - name: testventil_2
        state: "{{ is_state('input_boolean.v2','on') }}"
        turn_on: {action: input_boolean.turn_on, target: {entity_id: input_boolean.v2}}
        turn_off: {action: input_boolean.turn_off, target: {entity_id: input_boolean.v2}}
      - name: testventil_3
        state: "{{ is_state('input_boolean.v3','on') }}"
        turn_on: {action: input_boolean.turn_on, target: {entity_id: input_boolean.v3}}
        turn_off: {action: input_boolean.turn_off, target: {entity_id: input_boolean.v3}}
  - weather:
      - name: testwetter
        condition_template: "{{ 'sunny' }}"
        temperature_template: "{{ 25 }}"
        humidity_template: "{{ 40 }}"
        forecast_daily_template: >-
          {{ [ {'datetime': (now()+timedelta(days=0)).isoformat(), 'temperature': 27, 'templow': 15, 'precipitation': 0.0, 'condition': 'sunny'},
               {'datetime': (now()+timedelta(days=1)).isoformat(), 'temperature': 29, 'templow': 16, 'precipitation': 0.0, 'condition': 'sunny'},
               {'datetime': (now()+timedelta(days=2)).isoformat(), 'temperature': 24, 'templow': 14, 'precipitation': 1.2, 'condition': 'rainy'} ] }}
EOF

docker rm -f int-test >/dev/null 2>&1 || true
docker run -d --name int-test -p 127.0.0.1:8124:8123 -v "$TD":/config \
  ghcr.io/home-assistant/home-assistant:2026.6.3 >/dev/null
echo "HA bootet…"
python3 /tmp/int_test_driver.py
RC=$?
echo "--- relevante Fehler-Logs ---"
docker logs int-test 2>&1 | grep -iE "error|exception|traceback" | grep -iE "garten|config_flow|flow" | head -15 || echo "(keine)"
docker rm -f int-test >/dev/null
rm -rf "$TD"
exit $RC
