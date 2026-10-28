# 执行接口审计

{
  "utc": "2026-10-21T19:01:17.224383+00:00",
  "new_modes_executable": true,
  "zero_reproduces_strong": true,
  "observed_issued_reference_contrast_rank": 8,
  "singular_values": [
    2.0588636099016733,
    1.8410129849408,
    0.2984057826337333,
    0.24004971872000144,
    0.17966655229256775,
    0.1536718938774501,
    0.13017172135536062,
    0.053581976148083514
  ],
  "interventions": [
    {
      "id": "RETIMED_MODE0",
      "complete": true,
      "qualified": true,
      "JF": 1400.280740785643,
      "JM": 107.71136171915573,
      "accepted_and_activated": 4,
      "failed": [],
      "reference_delta_max_rad": 0.005267517318563897,
      "applied_torque_delta_max_Nm": 2.1353278150607764,
      "native_Human_delta_max": 0.020257272383053165,
      "executable": true
    },
    {
      "id": "RETIMED_MODE1",
      "complete": true,
      "qualified": true,
      "JF": 1399.8540368858696,
      "JM": 107.77968054128446,
      "accepted_and_activated": 4,
      "failed": [],
      "reference_delta_max_rad": 0.009583838123985,
      "applied_torque_delta_max_Nm": 2.181667470280594,
      "native_Human_delta_max": 0.019865893921312452,
      "executable": true
    },
    {
      "id": "RETIMED_MODE2",
      "complete": true,
      "qualified": true,
      "JF": 1400.0776157029122,
      "JM": 107.81800691983446,
      "accepted_and_activated": 5,
      "failed": [],
      "reference_delta_max_rad": 0.005434592855407566,
      "applied_torque_delta_max_Nm": 1.1403885392677466,
      "native_Human_delta_max": 0.01590189416874266,
      "executable": true
    },
    {
      "id": "RETIMED_MODE3",
      "complete": true,
      "qualified": true,
      "JF": 1400.783484439302,
      "JM": 107.6239349422261,
      "accepted_and_activated": 5,
      "failed": [],
      "reference_delta_max_rad": 0.005519238119180148,
      "applied_torque_delta_max_Nm": 1.1538547097175638,
      "native_Human_delta_max": 0.016199950767193362,
      "executable": true
    },
    {
      "id": "RETIMED_MODE4",
      "complete": true,
      "qualified": true,
      "JF": 1402.2012225369435,
      "JM": 107.87626455519246,
      "accepted_and_activated": 4,
      "failed": [],
      "reference_delta_max_rad": 0.036987662764225826,
      "applied_torque_delta_max_Nm": 4.7987723976559735,
      "native_Human_delta_max": 0.12467220573543313,
      "executable": true
    },
    {
      "id": "RETIMED_MODE5",
      "complete": true,
      "qualified": true,
      "JF": 1400.5328341647833,
      "JM": 106.93611188819627,
      "accepted_and_activated": 5,
      "failed": [],
      "reference_delta_max_rad": 0.03120175022892624,
      "applied_torque_delta_max_Nm": 4.700883517178937,
      "native_Human_delta_max": 0.06288791815247308,
      "executable": true
    },
    {
      "id": "RETIMED_MODE6",
      "complete": true,
      "qualified": true,
      "JF": 1401.0236207401817,
      "JM": 107.76672461925402,
      "accepted_and_activated": 4,
      "failed": [],
      "reference_delta_max_rad": 0.01991802155937239,
      "applied_torque_delta_max_Nm": 3.1783689716769246,
      "native_Human_delta_max": 0.05969691434978899,
      "executable": true
    },
    {
      "id": "RETIMED_MODE7",
      "complete": true,
      "qualified": true,
      "JF": 1400.4803840299435,
      "JM": 107.59603009620734,
      "accepted_and_activated": 5,
      "failed": [],
      "reference_delta_max_rad": 0.008695254266465113,
      "applied_torque_delta_max_Nm": 2.8910606093481874,
      "native_Human_delta_max": 0.016549862897017154,
      "executable": true
    }
  ],
  "original_safety_and_motion_contract_preserved": true,
  "contrast_scope": "eight separate one-mode actual issued-reference changes at common grid; finite local numerical rank",
  "fixed_vs_retimed_common": {
    "fixed": {
      "id": "RETIMED_FIXED_COMMON_POS",
      "action": {
        "family": "modal8",
        "x": [
          0.35,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        "legacy": [
          0.8245887463260377,
          -0.9835625245511301
        ]
      },
      "category": "engineering",
      "complete": true,
      "qualified": true,
      "error": null,
      "prediction": null,
      "wall_s": 105.90828275680542,
      "actual_new_native_steps": 69260,
      "JF": 1400.0897282599763,
      "JM": 107.70468785100465,
      "worst_ratio": 0.9557513459301377,
      "motion_vs_B": {
        "candidate": "RETIMED_FIXED_COMMON_POS",
        "B": "RETIMED_B",
        "acceptance_pass": true,
        "failed_requirements": [],
        "gain_N_s": 36.366769885074746,
        "gain_percent": 2.5317000502303055,
        "burden_ratios": {
          "velocity_deg_s/max_abs": [
            0.9808757817707318,
            0.9978568254688565
          ],
          "velocity_deg_s/p95_abs": [
            0.9898740334448899,
            1.044052857345182
          ],
          "velocity_deg_s/rms": [
            0.995326749054268,
            1.030332349455784
          ],
          "acceleration_deg_s2/max_abs": [
            0.8547169700932681,
            0.5482103747707029
          ],
          "acceleration_deg_s2/p95_abs": [
            0.9582823159320085,
            1.0227186181118202
          ],
          "acceleration_deg_s2/rms": [
            0.8504523162387462,
            0.7721402929213881
          ],
          "jerk_deg_s3/p95_abs": [
            0.8889148059769184,
            0.8935765868443613
          ],
          "jerk_deg_s3/rms": [
            1.047501925455982,
            0.9463785450211332
          ]
        },
        "burden_sensitivity": {
          "1.0": false,
          "1.05": true,
          "1.1": true,
          "1.25": true
        },
        "excursion_delta_deg": [
          0.15715549907964999,
          0.4716740390098835
        ],
        "cumulative_ratio": [
          0.9975613297845568,
          1.0035389132266446
        ],
        "endpoint_abs_delta_deg": [
          0.0011441291332339176,
          0.001065446890835986
        ],
        "phase_boundary_max_delta_deg": 0.0011441291332339176,
        "phase_shape_max_delta_deg": 14.277258818371454,
        "phase_shape_diagnostic": {
          "0.5": false,
          "1.0": false,
          "2.0": false
        },
        "duration_abs_delta_s": 0.0,
        "phase_J_F_delta_N_s": {
          "OUTBOUND": -13.807992472989895,
          "HOLD": -9.336504959378544e-06,
          "RETURN": -22.55876807557968
        },
        "moment_integral_ratio": 1.0637111888681139,
        "force_peak_delta_N": -0.8855694781215675,
        "moment_peak_delta_Nm": 0.0,
        "clock": "SCIENTIFIC_SIMULATION",
        "HOST_EXECUTION_CAUSAL_VALID": "NOT_EVALUABLE",
        "evaluator_binding": "identical prior thresholds and formulas, only ownership field bound to original scientific-mode native receipt audit",
        "symmetric_phase_decomposition": {
          "OUTBOUND": {
            "delta_J_F_N_s": -13.807992472989895,
            "duration_contribution_N_s": 0.0,
            "mean_force_contribution_N_s": -13.807992472989998
          },
          "HOLD": {
            "delta_J_F_N_s": -9.336504959378544e-06,
            "duration_contribution_N_s": 0.0,
            "mean_force_contribution_N_s": -9.336504955870412e-06
          },
          "RETURN": {
            "delta_J_F_N_s": -22.55876807557968,
            "duration_contribution_N_s": 0.0,
            "mean_force_contribution_N_s": -22.558768075579675
          }
        }
      },
      "axes": {
        "PHYSICAL_TASK_VALID": "PASS",
        "SCIENTIFIC_EXECUTION_CAUSAL_VALID": "PASS",
        "HOST_EXECUTION_CAUSAL_VALID": "NOT_EVALUABLE",
        "LEGACY_R2_MATCHED": "PASS"
      },
      "metrics_path": "runtime/reports/RETIMED_FIXED_COMMON_POS_MEASURED.json",
      "branch": {
        "clock": "SCIENTIFIC_SIMULATION",
        "phase": "OUTBOUND",
        "physical_time_s": 11.764999999995256,
        "native_hash": "08381b5f83edb9b9758d1cf8bcebc1e9305d4d234c0cc314d0ec897289ac84a2",
        "full_hash": "b4f525f59fbc87c1f4b2f3bc781cd9140fb60e8d14c71eaed4384a87232c99c0",
        "native_state_mask": 16383,
        "count": {
          "OUTBOUND": 1,
          "RETURN": 0
        },
        "commissioned_beta": [
          1.4451233039097302,
          0.20161343448443397,
          0.33970720234971163,
          33.481194688226964,
          7.74851971731362,
          10.159575041330715,
          9.987000154964967,
          1.4653489446915828,
          1.598634522909194,
          5.241074508782824,
          4.969099460375576
        ],
        "commissioned_residual": [
          [
            0.012653188793919502,
            -0.0051336216765736345,
            -0.006099410209382203,
            0.01070013625201122,
            0.01487399401243008
          ],
          [
            -0.001760747453369063,
            0.001784680524449029,
            0.00029423100439591305,
            -0.0032114623696964106,
            -0.0030138804564074782
          ]
        ],
        "prefix": {
          "OUTBOUND": [
            [
              0.08,
              0.04,
              0.03
            ]
          ],
          "RETURN": [
            [
              0.04,
              0.02,
              0.03
            ]
          ]
        }
      },
      "execution": [
        {
          "decision_index": 1,
          "activated": true,
          "modal": {
            "endpoints_and_HOLD_preserved": true,
            "fresh_original_certificate": true,
            "original_duration_s": 1.365,
            "original_pass_velocity": [
              0.28786162583682307,
              0.3461290432152771
            ],
            "original_target_rad": [
              0.9740507930076365,
              0.8885930674038122
            ],
            "parameters": [
              0.35,
              0.0,
              0.0,
              0.0,
              0.0,
              0.0,
              0.0,
              0.0
            ],
            "phase": "OUTBOUND",
            "proposed_duration_s": 1.365,
            "proposed_pass_velocity": [
              0.28786162583682307,
              0.3461290432152771
            ],
            "proposed_target_rad": [
              0.9749670908649336,
              0.8895093652611092
            ],
            "reason": "fixed-duration reference exceeds registered velocity limits",
            "schema": "acl2.modal.v1",
            "slot": 1,
            "status": "REJECTED",
            "truth_used": false,
            "weight": 0.4999999999999999
          },
          "legacy": {
            "common_shift": 0.010442415436364172,
            "continuous_realization": "unchanged certified quintic; polynomial spatial intent and velocity tilt",
            "differential_shift": 0.01515851527122428,
            "native_B_interface": false,
            "original_target": [
              0.9226664317790674,
              0.8976473291006298
            ],
            "parameters": [
              0.011522918251114749,
              0.015941601824945285,
              -0.004263005325384552,
              0.19961582684899362,
              0.1991996794524442,
              0.0035404128424628,
              -0.0032061779569697688,
              0.015085898039380494,
              0.07033365560184397,
              0.10095069730400985,
              -0.00039237820313586233,
              0.000621357826705337,
              0.0013767304750139104,
              -0.051504894499014714,
              0.00013709922513502714,
              -0.0007579181605806982,
              -0.0003439319818019933,
              -0.01209327626005151
            ],
            "proposed_target": [
              0.9740507930076365,
              0.8885930674038122
            ],
            "reason": null,
            "status": "ACCEPTED"
          },
          "reference_start_s": 11.769999999995244,
          "reference_end_s": 13.189999999991935
        },
        {
          "decision_index": 2,
          "activated": true,
          "modal": {
            "endpoints_and_HOLD_preserved": true,
            "fresh_original_certificate": true,
            "original_duration_s": 1.2650000000000001,
            "original_pass_velocity": [
              0.28063296121184594,
              0.35277809481039835
            ],
            "original_target_rad": [
              1.4181645760049435,
              1.2573058866241196
            ],
            "parameters": [
              0.35,
              0.0,
              0.0,
              0.0,
              0.0,
              0.0,
              0.0,
              0.0
            ],
            "phase": "OUTBOUND",
            "proposed_duration_s": 1.2650000000000001,
            "proposed_pass_velocity": [
              0.28063296121184594,
              0.35277809481039835
            ],
            "proposed_target_rad": [
              1.419874411084093,
              1.2590157217032691
            ],
            "reason": "fixed-duration reference exceeds registered velocity limits",
            "schema": "acl2.modal.v1",
            "slot": 2,
            "status": "REJECTED",
            "truth_used": false,
            "weight": 0.9330127018922194
          },
          "legacy": {
            "common_shift": 0.010303877666383321,
            "continuous_realization": "unchanged certified quintic; polynomial spatial intent and velocity tilt",
            "differential_shift": 0.013584817907347077,
            "native_B_interface": false,
            "original_target": [
              1.3702168909516015,
              1.2636048396983788
            ],
            "parameters": [
              0.011522918251114749,
              0.015941601824945285,
              -0.004263005325384552,
              0.19961582684899362,
              0.1991996794524442,
              0.0035404128424628,
              -0.0032061779569697688,
              0.015085898039380494,
              0.07033365560184397,
              0.10095069730400985,
              -0.00039237820313586233,
              0.000621357826705337,
              0.0013767304750139104,
              -0.051504894499014714,
              0.00013709922513502714,
              -0.0007579181605806982,
              -0.0003439319818019933,
              -0.01209327626005151
            ],
            "proposed_target": [
              1.4181645760049435,
              1.2573058866241196
            ],
            "reason": null,
            "status": "ACCEPTED"
          },
          "reference_start_s": 13.189999999991935,
          "reference_end_s": 14.509999999988858
        },
        {
          "decision_index": 3,
          "activated": true,
          "modal": {
            "endpoints_and_HOLD_preserved": true,
            "fresh_original_certificate": true,
            "original_duration_s": 1.22,
            "original_pass_velocity": [
              0.23300207742721835,
              0.35256574154296694
            ],
            "original_target_rad": [
              1.8297087764262496,
              1.6299355830407252
            ],
            "parameters": [
              0.35,
              0.0,
              0.0,
              0.0,
              0.0,
              0.0,
              0.0,
              0.0
            ],
            "phase": "OUTBOUND",
            "proposed_duration_s": 1.22,
            "proposed_pass_velocity": [
              0.23300207742721835,
              0.35256574154296694
            ],
            "proposed_target_rad": [
              1.8314186115053992,
              1.6316454181198747
            ],
            "reason": "fixed-duration reference exceeds registered velocity limits",
            "schema": "acl2.modal.v1",
            "slot": 3,
            "status": "REJECTED",
            "truth_used": false,
            "weight": 0.9330127018922194
          },
          "legacy": {
            "common_shift": 0.003657711640089586,
            "continuous_realization": "unchanged certified quintic; polynomial spatial intent and velocity tilt",
            "differential_shift": 0.0043920829577414,
            "native_B_interface": false,
            "original_target": [
              1.8135518031444882,
              1.631345474757501
            ],
            "parameters": [
              0.011522918251114749,
              0.015941601824945285,
              -0.004263005325384552,
              0.19961582684899362,
              0.1991996794524442,
              0.0035404128424628,
              -0.0032061779569697688,
              0.015085898039380494,
              0.07033365560184397,
              0.10095069730400985,
              -0.00039237820313586233,
              0.000621357826705337,
              0.0013767304750139104,
              -0.051504894499014714,
              0.00013709922513502714,
              -0.0007579181605806982,
              -0.0003439319818019933,
              -0.01209327626005151
            ],
            "proposed_target": [
              1.8297087764262496,
              1.6299355830407252
            ],
            "reason": null,
            "status": "ACCEPTED"
          },
          "reference_start_s": 14.509999999988858,
          "reference_end_s": 15.784999999985887
        },
        {
          "decision_index": 4,
          "activated": true,
          "modal": {
            "endpoints_and_HOLD_preserved": true,
            "fresh_original_certificate": true,
            "original_duration_s": 1.0,
            "original_pass_velocity": [
              0.0,
              0.34916251965084877
            ],
            "original_target_rad": [
              2.0943951023931953,
              2.0028581972517845
            ],
            "parameters": [
              0.35,
              0.0,
              0.0,
              0.0,
              0.0,
              0.0,
              0.0,
              0.0
            ],
            "phase": "OUTBOUND",
            "proposed_duration_s": 1.0,
            "proposed_pass_velocity": [
              0.0,
              0.34916251965084877
            ],
            "proposed_target_rad": [
              2.0953114002504925,
              2.0037744951090817
            ],
            "reason": "fixed-duration reference exceeds registered velocity limits",
            "schema": "acl2.modal.v1",
            "slot": 4,
            "status": "REJECTED",
            "truth_used": false,
            "weight": 0.5000000000000001
          },
          "legacy": {
            "parameters": [
              0.011522918251114749,
              0.015941601824945285,
              -0.004263005325384552,
              0.19961582684899362,
              0.1991996794524442,
              0.0035404128424628,
              -0.0032061779569697688,
              0.015085898039380494,
              0.07033365560184397,
              0.10095069730400985,
              -0.00039237820313586233,
              0.000621357826705337,
              0.0013767304750139104,
              -0.051504894499014714,
              0.00013709922513502714,
              -0.0007579181605806982,
              -0.0003439319818019933,
              -0.01209327626005151
            ],
            "reason": "NORMALIZED_TARGET_OUT_OF_RANGE",
            "status": "REJECTED"
          },
          "reference_start_s": 15.784999999985887,
          "reference_end_s": 16.83499999998937
        },
        {
          "decision_index": 8,
          "activated": true,
          "modal": {
            "endpoints_and_HOLD_preserved": true,
            "fresh_original_certificate": true,
            "original_duration_s": 1.61,
            "original_pass_velocity": [
              -0.22250436871013982,
              -0.3444499383660859
            ],
            "original_target_rad": [
              1.685399453780998,
              1.7125803987908967
            ],
            "parameters": [
              0.35,
              0.0,
              0.0,
              0.0,
              0.0,
              0.0,
              0.0,
              0.0
            ],
            "phase": "RETURN",
            "proposed_duration_s": 1.61,
            "proposed_pass_velocity": [
              -0.22250436871013982,
              -0.3444499383660859
            ],
            "proposed_target_rad": [
              1.685399453780998,
              1.7125803987908967
            ],
            "reason": null,
            "schema": "acl2.modal.v1",
            "slot": 0,
            "status": "ACCEPTED",
            "truth_used": false,
            "weight": 0.06698729810778066
          },
          "legacy": null,
          "reference_start_s": 20.080000000004866,
          "reference_end_s": 21.7000000000126
        },
        {
          "decision_index": 9,
          "activated": true,
          "modal": {
            "endpoints_and_HOLD_preserved": true,
            "fresh_original_certificate": true,
            "original_duration_s": 1.19,
            "original_pass_velocity": [
              -0.24236047114889483,
              -0.3386321859436468
            ],
            "original_target_rad": [
              1.3338688760118826,
              1.2850628264974446
            ],
            "parameters": [
              0.35,
              0.0,
              0.0,
              0.0,
              0.0,
              0.0,
              0.0,
              0.0
            ],
            "phase": "RETURN",
            "proposed_duration_s": 1.19,
            "proposed_pass_velocity": [
              -0.24236047114889483,
              -0.3386321859436468
            ],
            "proposed_target_rad": [
              1.3338688760118826,
              1.2850628264974446
            ],
            "reason": null,
            "schema": "acl2.modal.v1",
            "slot": 1,
            "status": "ACCEPTED",
            "truth_used": false,
            "weight": 0.4999999999999999
          },
          "legacy": null,
          "reference_start_s": 21.7000000000126,
          "reference_end_s": 22.94000000001852
        },
        {
          "decision_index": 10,
          "activated": true,
          "modal": {
            "endpoints_and_HOLD_preserved": true,
            "fresh_original_certificate": true,
            "original_duration_s": 1.08,
            "original_pass_velocity": [
              -0.24148536559950798,
              -0.3401419931779835
            ],
            "original_target_rad": [
              0.9818994922696133,
              0.8575436443643653
            ],
            "parameters": [
              0.35,
              0.0,
              0.0,
              0.0,
              0.0,
              0.0,
              0.0,
              0.0
            ],
            "phase": "RETURN",
            "proposed_duration_s": 1.08,
            "proposed_pass_velocity": [
              -0.24148536559950798,
              -0.3401419931779835
            ],
            "proposed_target_rad": [
              0.9818994922696133,
              0.8575436443643653
            ],
            "reason": null,
            "schema": "acl2.modal.v1",
            "slot": 2,
            "status": "ACCEPTED",
            "truth_used": false,
            "weight": 0.9330127018922194
          },
          "legacy": null,
          "reference_start_s": 22.94000000001852,
          "reference_end_s": 24.070000000023917
        },
        {
          "decision_index": 11,
          "activated": true,
          "modal": {
            "endpoints_and_HOLD_preserved": true,
            "fresh_original_certificate": true,
            "original_duration_s": 1.24,
            "original_pass_velocity": [
              -0.2216979538950966,
              -0.34614649349930043
            ],
            "original_target_rad": [
              0.5850013208616135,
              0.48041957780000566
            ],
            "parameters": [
              0.35,
              0.0,
              0.0,
              0.0,
              0.0,
              0.0,
              0.0,
              0.0
            ],
            "phase": "RETURN",
            "proposed_duration_s": 1.24,
            "proposed_pass_velocity": [
              -0.2216979538950966,
              -0.34614649349930043
            ],
            "proposed_target_rad": [
              0.5850013208616135,
              0.48041957780000566
            ],
            "reason": null,
            "schema": "acl2.modal.v1",
            "slot": 3,
            "status": "ACCEPTED",
            "truth_used": false,
            "weight": 0.9330127018922194
          },
          "legacy": null,
          "reference_start_s": 24.070000000023917,
          "reference_end_s": 25.360000000030077
        },
        {
          "decision_index": 12,
          "activated": true,
          "modal": {
            "endpoints_and_HOLD_preserved": true,
            "fresh_original_certificate": true,
            "original_duration_s": 1.5150000000000001,
            "original_pass_velocity": [
              -0.20960671895787836,
              0.0
            ],
            "original_target_rad": [
              0.18679983723367855,
              0.16580627893946132
            ],
            "parameters": [
              0.35,
              0.0,
              0.0,
              0.0,
              0.0,
              0.0,
              0.0,
              0.0
            ],
            "phase": "RETURN",
            "proposed_duration_s": 1.5150000000000001,
            "proposed_pass_velocity": [
              -0.20960671895787836,
              0.0
            ],
            "proposed_target_rad": [
              0.18679983723367855,
              0.16580627893946132
            ],
            "reason": null,
            "schema": "acl2.modal.v1",
            "slot": 4,
            "status": "ACCEPTED",
            "truth_used": false,
            "weight": 0.5000000000000001
          },
          "legacy": null,
          "reference_start_s": 25.360000000030077,
          "reference_end_s": 26.92500000003755
        }
      ],
      "tracking": [
        0.4516539127636881,
        0.5323400044817005
      ],
      "phase_cost": {
        "OUTBOUND": {
          "J_F_N_s": 706.0600914551994,
          "moment_integral_Nm_s": 48.928619838929244,
          "integrated_trace_duration_s": 9.005000000000718,
          "phase_clock_duration_s": 9.005000000000718,
          "mean_force_N": 78.40756151639567,
          "mean_moment_Nm": 5.433494707265446,
          "force_peak_N": 113.72164577099606,
          "moment_peak_Nm": 15.515711683982877
        },
        "HOLD": {
          "J_F_N_s": 54.39433075293617,
          "moment_integral_Nm_s": 1.2187085743475057,
          "integrated_trace_duration_s": 1.0200000000048703,
          "phase_clock_duration_s": 1.0200000000048703,
          "mean_force_N": 53.32777524772201,
          "mean_moment_Nm": 1.1948123277859672,
          "force_peak_N": 53.32778160380789,
          "moment_peak_Nm": 1.1948135055949822
        },
        "RETURN": {
          "J_F_N_s": 639.6353060518409,
          "moment_integral_Nm_s": 57.557359437727925,
          "integrated_trace_duration_s": 9.005000000042997,
          "phase_clock_duration_s": 9.005000000042997,
          "mean_force_N": 71.03112782329669,
          "mean_moment_Nm": 6.391711209045319,
          "force_peak_N": 88.98790069646495,
          "moment_peak_Nm": 13.099516728798928
        }
      }
    },
    "retimed": {
      "id": "RETIMED_MODE0",
      "action": {
        "family": "modal8_retimed",
        "x": [
          0.35,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0,
          0.0
        ],
        "legacy": [
          0.8245887463260377,
          -0.9835625245511301
        ]
      },
      "category": "engineering",
      "complete": true,
      "qualified": true,
      "error": null,
      "prediction": null,
      "wall_s": 104.56597375869751,
      "actual_new_native_steps": 69260,
      "JF": 1400.280740785643,
      "JM": 107.71136171915573,
      "worst_ratio": 0.9658537250035748,
      "motion_vs_B": {
        "candidate": "RETIMED_MODE0",
        "B": "RETIMED_B",
        "acceptance_pass": true,
        "failed_requirements": [],
        "gain_N_s": 36.17575735940795,
        "gain_percent": 2.5184025695259855,
        "burden_ratios": {
          "velocity_deg_s/max_abs": [
            0.9812567885624225,
            0.9978568254817916
          ],
          "velocity_deg_s/p95_abs": [
            0.9894650857313001,
            1.0624390975039324
          ],
          "velocity_deg_s/rms": [
            0.9952247169659414,
            1.0314389965936637
          ],
          "acceleration_deg_s2/max_abs": [
            0.8695106849546258,
            0.5542020684465142
          ],
          "acceleration_deg_s2/p95_abs": [
            0.9592294570622794,
            1.0184256215812677
          ],
          "acceleration_deg_s2/rms": [
            0.8519220290334031,
            0.7779944633225409
          ],
          "jerk_deg_s3/p95_abs": [
            0.8939752084368765,
            0.8957253461939926
          ],
          "jerk_deg_s3/rms": [
            1.0478524612418953,
            0.9467086563091285
          ]
        },
        "burden_sensitivity": {
          "1.0": false,
          "1.05": false,
          "1.1": true,
          "1.25": true
        },
        "excursion_delta_deg": [
          0.15137836250414693,
          0.47956073678703603
        ],
        "cumulative_ratio": [
          0.9975817795312361,
          1.0036178303338184
        ],
        "endpoint_abs_delta_deg": [
          0.001144129137791161,
          0.0010654468919053528
        ],
        "phase_boundary_max_delta_deg": 0.001144129137791161,
        "phase_shape_max_delta_deg": 14.277258816482671,
        "phase_shape_diagnostic": {
          "0.5": false,
          "1.0": false,
          "2.0": false
        },
        "duration_abs_delta_s": 0.0,
        "phase_J_F_delta_N_s": {
          "OUTBOUND": -13.61698041583611,
          "HOLD": -8.8544840153304e-06,
          "RETURN": -22.558768089087266
        },
        "moment_integral_ratio": 1.0637771012101576,
        "force_peak_delta_N": -0.9148796570862885,
        "moment_peak_delta_Nm": 0.0,
        "clock": "SCIENTIFIC_SIMULATION",
        "HOST_EXECUTION_CAUSAL_VALID": "NOT_EVALUABLE",
        "evaluator_binding": "identical prior thresholds and formulas, only ownership field bound to original scientific-mode native receipt audit",
        "symmetric_phase_decomposition": {
          "OUTBOUND": {
            "delta_J_F_N_s": -13.61698041583611,
            "duration_contribution_N_s": 0.0,
            "mean_force_contribution_N_s": -13.61698041583621
          },
          "HOLD": {
            "delta_J_F_N_s": -8.8544840153304e-06,
            "duration_contribution_N_s": 0.0,
            "mean_force_contribution_N_s": -8.854484018783283e-06
          },
          "RETURN": {
            "delta_J_F_N_s": -22.558768089087266,
            "duration_contribution_N_s": 0.0,
            "mean_force_contribution_N_s": -22.55876808908716
          }
        }
      },
      "axes": {
        "PHYSICAL_TASK_VALID": "PASS",
        "SCIENTIFIC_EXECUTION_CAUSAL_VALID": "PASS",
        "HOST_EXECUTION_CAUSAL_VALID": "NOT_EVALUABLE",
        "LEGACY_R2_MATCHED": "PASS"
      },
      "metrics_path": "runtime/reports/RETIMED_MODE0_MEASURED.json",
      "branch": {
        "clock": "SCIENTIFIC_SIMULATION",
        "phase": "OUTBOUND",
        "physical_time_s": 11.764999999995256,
        "native_hash": "08381b5f83edb9b9758d1cf8bcebc1e9305d4d234c0cc314d0ec897289ac84a2",
        "full_hash": "b4f525f59fbc87c1f4b2f3bc781cd9140fb60e8d14c71eaed4384a87232c99c0",
        "native_state_mask": 16383,
        "count": {
          "OUTBOUND": 1,
          "RETURN": 0
        },
        "commissioned_beta": [
          1.4451233039097302,
          0.20161343448443397,
          0.33970720234971163,
          33.481194688226964,
          7.74851971731362,
          10.159575041330715,
          9.987000154964967,
          1.4653489446915828,
          1.598634522909194,
          5.241074508782824,
          4.969099460375576
        ],
        "commissioned_residual": [
          [
            0.012653188793919502,
            -0.0051336216765736345,
            -0.006099410209382203,
            0.01070013625201122,
            0.01487399401243008
          ],
          [
            -0.001760747453369063,
            0.001784680524449029,
            0.00029423100439591305,
            -0.0032114623696964106,
            -0.0030138804564074782
          ]
        ],
        "prefix": {
          "OUTBOUND": [
            [
              0.08,
              0.04,
              0.03
            ]
          ],
          "RETURN": [
            [
              0.04,
              0.02,
              0.03
            ]
          ]
        }
      },
      "execution": [
        {
          "decision_index": 1,
          "activated": true,
          "modal": {
            "actually_selected_duration_s": 1.37,
            "actually_selected_pass_velocity": [
              0.28786162583682307,
              0.3461290432152771
            ],
            "actually_selected_target_rad": [
              0.9749670908649336,
              0.8895093652611092
            ],
            "endpoints_and_HOLD_preserved": true,
            "fresh_original_certificate": true,
            "individual_joint_endpoint_locks": [
              false,
              false
            ],
            "original_duration_s": 1.365,
            "original_pass_velocity": [
              0.28786162583682307,
              0.3461290432152771
            ],
            "original_target_rad": [
              0.9740507930076365,
              0.8885930674038122
            ],
            "parameters": [
              0.35,
              0.0,
              0.0,
              0.0,
              0.0,
              0.0,
              0.0,
              0.0
            ],
            "phase": "OUTBOUND",
            "proposed_duration_s": 1.365,
            "proposed_pass_velocity": [
              0.28786162583682307,
              0.3461290432152771
            ],
            "proposed_target_rad": [
              0.9749670908649336,
              0.8895093652611092
            ],
            "reason": null,
            "scheduler_duration_record": {
              "original_parent_duration_s": 1.365,
              "original_scheduler_minimum_s": 1.37,
              "requested_duration_s": 1.37,
              "requested_factor": 1.0,
              "safety_limits_unchanged": true
            },
            "schema": "acl2.modal.retimed.v2",
            "slot": 1,
            "status": "ACCEPTED",
            "truth_used": false,
            "weight": 0.4999999999999999
          },
          "legacy": null,
          "reference_start_s": 11.769999999995244,
          "reference_end_s": 13.194999999991923
        },
        {
          "decision_index": 2,
          "activated": true,
          "modal": {
            "actually_selected_duration_s": 1.27,
            "actually_selected_pass_velocity": [
              0.2805489452643579,
              0.3527884158965303
            ],
            "actually_selected_target_rad": [
              1.4207207904327377,
              1.2599416817006515
            ],
            "endpoints_and_HOLD_preserved": true,
            "fresh_original_certificate": true,
            "individual_joint_endpoint_locks": [
              false,
              false
            ],
            "original_duration_s": 1.2650000000000001,
            "original_pass_velocity": [
              0.2805489452643579,
              0.3527884158965303
            ],
            "original_target_rad": [
              1.4190109553535881,
              1.258231846621502
            ],
            "parameters": [
              0.35,
              0.0,
              0.0,
              0.0,
              0.0,
              0.0,
              0.0,
              0.0
            ],
            "phase": "OUTBOUND",
            "proposed_duration_s": 1.2650000000000001,
            "proposed_pass_velocity": [
              0.2805489452643579,
              0.3527884158965303
            ],
            "proposed_target_rad": [
              1.4207207904327377,
              1.2599416817006515
            ],
            "reason": null,
            "scheduler_duration_record": {
              "original_parent_duration_s": 1.2650000000000001,
              "original_scheduler_minimum_s": 1.27,
              "requested_duration_s": 1.27,
              "requested_factor": 1.0,
              "safety_limits_unchanged": true
            },
            "schema": "acl2.modal.retimed.v2",
            "slot": 2,
            "status": "ACCEPTED",
            "truth_used": false,
            "weight": 0.9330127018922194
          },
          "legacy": null,
          "reference_start_s": 13.194999999991923,
          "reference_end_s": 14.519999999988835
        },
        {
          "decision_index": 3,
          "activated": true,
          "modal": {
            "actually_selected_duration_s": 1.225,
            "actually_selected_pass_velocity": [
              0.23271034304695987,
              0.3525375597292604
            ],
            "actually_selected_target_rad": [
              1.8337701472759391,
              1.6342953347642895
            ],
            "endpoints_and_HOLD_preserved": true,
            "fresh_original_certificate": true,
            "individual_joint_endpoint_locks": [
              false,
              false
            ],
            "original_duration_s": 1.22,
            "original_pass_velocity": [
              0.23271034304695987,
              0.3525375597292604
            ],
            "original_target_rad": [
              1.8320603121967896,
              1.6325854996851399
            ],
            "parameters": [
              0.35,
              0.0,
              0.0,
              0.0,
              0.0,
              0.0,
              0.0,
              0.0
            ],
            "phase": "OUTBOUND",
            "proposed_duration_s": 1.22,
            "proposed_pass_velocity": [
              0.23271034304695987,
              0.3525375597292604
            ],
            "proposed_target_rad": [
              1.8337701472759391,
              1.6342953347642895
            ],
            "reason": null,
            "scheduler_duration_record": {
              "original_parent_duration_s": 1.22,
              "original_scheduler_minimum_s": 1.225,
              "requested_duration_s": 1.225,
              "requested_factor": 1.0,
              "safety_limits_unchanged": true
            },
            "schema": "acl2.modal.retimed.v2",
            "slot": 3,
            "status": "ACCEPTED",
            "truth_used": false,
            "weight": 0.9330127018922194
          },
          "legacy": null,
          "reference_start_s": 14.519999999988835,
          "reference_end_s": 15.799999999985852
        },
        {
          "decision_index": 4,
          "activated": true,
          "modal": {
            "actually_selected_duration_s": 0.985,
            "actually_selected_pass_velocity": [
              0.0,
              0.3488616709773284
            ],
            "actually_selected_target_rad": [
              2.0943951023931953,
              2.0081179478128512
            ],
            "endpoints_and_HOLD_preserved": true,
            "fresh_original_certificate": true,
            "individual_joint_endpoint_locks": [
              true,
              false
            ],
            "original_duration_s": 0.985,
            "original_pass_velocity": [
              0.0,
              0.3488616709773284
            ],
            "original_target_rad": [
              2.0943951023931953,
              2.007201649955554
            ],
            "parameters": [
              0.35,
              0.0,
              0.0,
              0.0,
              0.0,
              0.0,
              0.0,
              0.0
            ],
            "phase": "OUTBOUND",
            "proposed_duration_s": 0.985,
            "proposed_pass_velocity": [
              0.0,
              0.3488616709773284
            ],
            "proposed_target_rad": [
              2.0943951023931953,
              2.0081179478128512
            ],
            "reason": null,
            "scheduler_duration_record": {
              "original_parent_duration_s": 0.985,
              "original_scheduler_minimum_s": 0.985,
              "requested_duration_s": 0.985,
              "requested_factor": 1.0,
              "safety_limits_unchanged": true
            },
            "schema": "acl2.modal.retimed.v2",
            "slot": 4,
            "status": "ACCEPTED",
            "truth_used": false,
            "weight": 0.5000000000000001
          },
          "legacy": null,
          "reference_start_s": 15.799999999985852,
          "reference_end_s": 16.83499999998937
        },
        {
          "decision_index": 8,
          "activated": true,
          "modal": null,
          "legacy": {
            "common_shift": 0.0011027593910589997,
            "continuous_realization": "unchanged certified quintic; polynomial spatial intent and velocity tilt",
            "differential_shift": -0.004283521752933491,
            "native_B_interface": false,
            "original_target": [
              1.6790152546319361,
              1.7229213162731525
            ],
            "parameters": [
              0.011522918251114749,
              0.015941601824945285,
              -0.004263005325384552,
              0.19961582684899362,
              0.1991996794524442,
              0.0035404128424628,
              -0.0032061779569697688,
              0.015085898039380494,
              0.07033365560184397,
              0.10095069730400985,
              -0.00039237820313586233,
              0.000621357826705337,
              0.0013767304750139104,
              -0.051504894499014714,
              0.00013709922513502714,
              -0.0007579181605806982,
              -0.0003439319818019933,
              -0.01209327626005151
            ],
            "proposed_target": [
              1.6853994538648316,
              1.7125803988290693
            ],
            "reason": null,
            "status": "ACCEPTED"
          },
          "reference_start_s": 20.080000000004866,
          "reference_end_s": 21.7000000000126
        }
      ],
      "tracking": [
        0.4516211984444319,
        0.532980482476438
      ],
      "phase_cost": {
        "OUTBOUND": {
          "J_F_N_s": 706.2511035123532,
          "moment_integral_Nm_s": 48.935293651304065,
          "integrated_trace_duration_s": 9.005000000000718,
          "phase_clock_duration_s": 9.005000000000718,
          "mean_force_N": 78.42877329398077,
          "mean_moment_Nm": 5.434235830238774,
          "force_peak_N": 113.69233559203134,
          "moment_peak_Nm": 15.515711683982877
        },
        "HOLD": {
          "J_F_N_s": 54.394331234957114,
          "moment_integral_Nm_s": 1.2187086314881816,
          "integrated_trace_duration_s": 1.0200000000048703,
          "phase_clock_duration_s": 1.0200000000048703,
          "mean_force_N": 53.327775720291555,
          "mean_moment_Nm": 1.1948123838062377,
          "force_peak_N": 53.327780998380405,
          "moment_peak_Nm": 1.1948133741773816
        },
        "RETURN": {
          "J_F_N_s": 639.6353060383333,
          "moment_integral_Nm_s": 57.55735943636347,
          "integrated_trace_duration_s": 9.005000000042997,
          "phase_clock_duration_s": 9.005000000042997,
          "mean_force_N": 71.03112782179669,
          "mean_moment_Nm": 6.391711208893797,
          "force_peak_N": 88.98790069483867,
          "moment_peak_Nm": 13.099516729539012
        }
      }
    }
  },
  "source_sha256": "a676b72e20ac84ff9efc290a91329fce2a3a92609e8d2d6ef8762866b57457ea",
  "same_family_coordinate_identity": true,
  "zero_reproduces_H150": true
}

完整 issued/accepted/activated/rejected/applied 身份在每条 summary、EXECUTION_BINDING、原 EXECUTED_RESIDUAL_RECEIPTS、runtime_artifacts 与独立raw重算中保留。参考合法与真实Human motion合格分别判断。
