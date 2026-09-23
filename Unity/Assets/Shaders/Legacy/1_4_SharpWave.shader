Shader "MasterProject/1_4_SharpWave" {

	Properties {
		_Diffuse ("Diffuse", Color) = (1, 1, 1, 1)
		_Gloss ("Gloss", Float) = 1.0
		_SpecPow ("Specular Power", Float) = 1.0
		_WaveInt ("Wave Intensity", Float) = 1.0
		_WaveFreq ("Wave Freqency", Float) = 1.0
		_WaveSpeed ("Wave Speed", Float) = 1.0
		_WaveAmount ("Wave Amount", Int) = 1
		_PeekSharp ("Peek Sharpness", Float) = 1.0
		_NormalInt ("Normal Intensity", Float) = 1.0
		_FBM_Int ("Fraction Brownian Motion Intensity", Range(0.0, 1.0)) = 0.82
		_FBM_Fre ("Fraction Brownian Motion Frequent", Range(1.0, 2.0)) = 1.18
		_FBM_Time ("Fraction Brownian Motion Time", Range(0.0, 2.0)) = 0.82
	}

	SubShader {

		Pass {

			Tags { "LightMode" = "ForwardBase" }
			Tags { "RenderType" = "Opaque" }
			LOD 200

			CGPROGRAM

				#pragma vertex vert
				#pragma fragment frag

				#pragma target 3.0

				#include "Lighting.cginc"

				float4 _Diffuse;
				float _Gloss;
				float _SpecPow;
				float _WaveInt;
				float _WaveFreq;
				float _WaveSpeed;
				int _WaveAmount;
				float _PeekSharp;
				float _NormalInt;
				float _FBM_Int;
				float _FBM_Fre;
				float _FBM_Time;

				float random(float2 seed){
					return frac(sin(dot(seed, float2(12.9898, 78.233))) * 43758.5453) * 360;
				}

                struct a2v{
                    float4 vertex : POSITION;
					float3 normal : NORMAL;

                };

                struct v2f{
                   float4 pos : SV_POSITION;
				   float3 worldNormal : TEXCOORD0;
				   float3 worldPos : TEXCOORD1;
                };

				v2f vert(a2v v) {

					v2f o;

					float wave = 0;
					float waveInt = _WaveInt * 0.1;
					float waveFreq = _WaveFreq;
					float waveSpeed = _WaveSpeed;
					float d_dx = 0;
					float d_dz = 0;
					float time = _Time.y * waveSpeed;
					
                    for (int i = 1; i <= _WaveAmount; i++) {

						//Generating a random direction for each wave
						float angle = radians(random(float2(i * 0.2, i * 0.2)));
						float cosA = cos(angle);
						float sinA = sin(angle);
						float rotatedX = v.vertex.x * cosA + v.vertex.z * sinA;

						//Generate a sine wave and introduce the effect of Fractional Brownian Motion
						float tempInt = waveInt * pow(_FBM_Int, i - 1);
						float tempFreq = waveFreq * pow(_FBM_Fre, i - 1);
						float tempTime = time * pow(_FBM_Time, i);
						float phase = rotatedX * tempFreq + tempTime;
						float expVal = exp(sin(phase) * _PeekSharp) - 1.0;

						//Accumulate waves
						wave += tempInt * expVal;

						//Calculate partial derivative for normal
						d_dx += tempInt * expVal * _PeekSharp * cos(phase) * cosA * tempFreq;
						d_dz += tempInt * expVal * _PeekSharp * cos(phase) * sinA * tempFreq;
					}
					//Apply normal and vertex offset
					v.normal = normalize(float3(-d_dx * _NormalInt, 1, -d_dz * _NormalInt));
					v.vertex.y += wave;		

					o.pos = UnityObjectToClipPos(v.vertex);
					o.worldPos = mul(unity_ObjectToWorld, v.vertex);

					o.worldNormal = normalize(mul((float3x3)unity_ObjectToWorld, v.normal));

					return o;
				
				}

				float4 frag(v2f i) : SV_Target {
					float3 worldNormal = normalize(i.worldNormal);

					float3 worldLightDir = normalize(_WorldSpaceLightPos0.xyz);

					float3 viewDir = normalize(_WorldSpaceCameraPos.xyz - i.worldPos);
					float3 halfDir = normalize(worldLightDir + viewDir);

					float3 spec = _SpecPow * pow(max(0, dot(worldNormal, halfDir)), _Gloss) * _LightColor0.rgb;
					float3 diffuse = _Diffuse.rgb * _LightColor0.rgb * saturate(dot(worldNormal, worldLightDir));
					float3 ambient = UNITY_LIGHTMODEL_AMBIENT.rgb;// + ShadeSH9(float4(worldNormal, 1.0));

					float3 color = diffuse + spec;// + ambient;

					return float4 (color, 1.0);
				}
			
			ENDCG

		}

	}
	Fallback "Diffuse"
}