      - type: hold_key
        key: a
        seconds: 0.5
      - type: start_continuous_input
        name: hold_s
        action: hold_key
        key: s
      - type: wait
        seconds: 8.0
      - type: press_key
        key: space
        seconds: 0.1
      - type: wait
        seconds: 0.4
      - type: press_key
        key: space
        seconds: 0.1
      - type: wait
        seconds: 1.0
      - type: stop_continuous_input
        name: hold_s
      - type: hold_key
        key: a
        seconds: 2.0
      - type: hold_key
        key: s
        seconds: 0.3
      - type: wait
        seconds: 1.0
      - type: hold_keys
        keys: [a, s, space]
        seconds: 1.0
      - type: hold_key
        key: a
        seconds: 1.0
      - type: hold_key
        key: s
        seconds: 0.5
      - type: wait
        seconds: 1.0
      - type: start_continuous_input
        name: hold_s_a
        action: hold_keys
        keys: [s, a]
        stop_after_seconds: 3.0
      - type: press_key
        key: space
        seconds: 0.1
      - type: wait
        seconds: 0.3
      - type: press_key
        key: space
        seconds: 0.1
      - type: wait
        seconds: 3.0
      - type: hold_key
        key: w
        seconds: 0.4
      - type: hold_key
        key: a
        seconds: 2.3
      - type: start_continuous_input
        name: hold_s
        action: hold_key
        key: s
      - type: wait
        seconds: 0.1
      - type: start_continuous_input
        name: press_left_shift
        action: press_key
        key: left_shift
        seconds: 0.1
        repeat_every_seconds: 0.2
      - type: start_continuous_input
        name: character_loop_cycle
        action: sequence
        sequence:
          - action: press_key
            key: "1"
            repeat_every_seconds: 0.1
            seconds: 0.1
            run_for_seconds: 1.0
          - action: press_key
            key: "2"
            repeat_every_seconds: 0.1
            seconds: 0.1
            run_for_seconds: 1.0
          - action: press_key
            key: "3"
            repeat_every_seconds: 0.1
            seconds: 0.1
            run_for_seconds: 1.0
          - action: press_key
            key: "4"
            repeat_every_seconds: 0.1
            seconds: 0.1
            run_for_seconds: 1.0
      - type: wait
        seconds: 5.0
      - type: stop_continuous_input
        name: character_loop_cycle
      - type: stop_continuous_input
        name: press_left_shift
      - type: stop_continuous_input
        name: hold_s
