using UnityEngine;
using System.Collections.Generic;
using System.Text;
using System.Reflection;

// READ-ONLY diagnostic. Measures per-frame claw stability AND traces one claw's axis frame-by-frame.
public class ClawFlickerProbe : MonoBehaviour
{
    public int windowFrames = 60;
    public bool done;
    public int framesSampled;
    public int minAlive = 999999, maxAlive = 0;
    public float maxPosDelta, avgPosDelta;
    public float maxRotDelta, avgRotDelta;
    public int matchedSamples;
    public int idChurnFrames;
    public string axisTrace = "";   // tracked claw's Y-axis + pos per frame

    MonoBehaviour _instancer;
    FieldInfo _bufField;
    Dictionary<int, Vector3> _prevPos = new Dictionary<int, Vector3>();
    Dictionary<int, Vector3> _prevAxis = new Dictionary<int, Vector3>();
    double _sumPos, _sumRot;
    int _trackedId = int.MinValue;
    StringBuilder _trace = new StringBuilder();
    int _traceCount;

    void Start()
    {
#if UNITY_EDITOR
        var BF = BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public;
        foreach (var mb in FindObjectsByType<MonoBehaviour>(FindObjectsSortMode.None))
            if (mb != null && mb.GetType().Name == "OceanClawGpuInstancer") { _instancer = mb; break; }
        if (_instancer != null) _bufField = _instancer.GetType().GetField("_instancesBuffer", BF);
#endif
    }

    void LateUpdate()
    {
#if UNITY_EDITOR
        if (done || _instancer == null || _bufField == null) return;
        var buf = _bufField.GetValue(_instancer) as ComputeBuffer;
        if (buf == null) return;
        int n = buf.count;
        float[] raw = new float[n * 20];
        buf.GetData(raw);

        var curPos = new Dictionary<int, Vector3>();
        var curAxis = new Dictionary<int, Vector3>();
        int alive = 0; bool churn = false;
        for (int i = 0; i < n; i++)
        {
            float life = raw[i * 20 + 17];
            if (life < 0.05f) continue;
            alive++;
            int id = Mathf.RoundToInt(raw[i * 20 + 18] * 1000000f);
            var pos = new Vector3(raw[i * 20 + 3], raw[i * 20 + 7], raw[i * 20 + 11]);
            var axisRaw = new Vector3(raw[i * 20 + 1], raw[i * 20 + 5], raw[i * 20 + 9]);
            var axis = axisRaw.sqrMagnitude > 1e-6f ? axisRaw.normalized : axisRaw;
            if (!curPos.ContainsKey(id)) { curPos[id] = pos; curAxis[id] = axis; }
            if (_prevPos.TryGetValue(id, out var pp))
            {
                float pd = (pos - pp).magnitude;
                float rd = Vector3.Angle(axis, _prevAxis[id]);
                _sumPos += pd; _sumRot += rd; matchedSamples++;
                if (pd > maxPosDelta) maxPosDelta = pd;
                if (rd > maxRotDelta) maxRotDelta = rd;
            }
            else churn = true;
            // pick + trace one stable claw
            if (_trackedId == int.MinValue) _trackedId = id;
            if (id == _trackedId && _traceCount < 16)
            {
                _trace.Append("f").Append(framesSampled).Append(" axis=(")
                    .Append(axis.x.ToString("F3")).Append(",").Append(axis.y.ToString("F3")).Append(",").Append(axis.z.ToString("F3"))
                    .Append(") |yMag=").Append(axisRaw.magnitude.ToString("F1"))
                    .Append(" pos=(").Append(pos.x.ToString("F1")).Append(",").Append(pos.z.ToString("F1")).Append(")\n");
                _traceCount++;
            }
        }
        if (alive < minAlive) minAlive = alive;
        if (alive > maxAlive) maxAlive = alive;
        if (churn && framesSampled > 0) idChurnFrames++;
        _prevPos = curPos; _prevAxis = curAxis;
        framesSampled++;
        if (framesSampled >= windowFrames)
        {
            avgPosDelta = matchedSamples > 0 ? (float)(_sumPos / matchedSamples) : 0f;
            avgRotDelta = matchedSamples > 0 ? (float)(_sumRot / matchedSamples) : 0f;
            axisTrace = _trace.ToString();
            done = true;
        }
#endif
    }
}
