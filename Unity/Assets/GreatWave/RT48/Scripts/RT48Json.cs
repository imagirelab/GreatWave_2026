using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text;

namespace GreatWave.RT48
{
    // RT48：小さな JSON の読み手（入れ子の配列と、キーが数の辞書を読むため。JsonUtility では読めない）。
    // 物 → Dictionary<string, object>、配列 → List<object>、数 → double、文字 → string、true/false → bool、null → null。
    // Python の json が書く NaN・Infinity・-Infinity も読む。
    public static class RT48Json
    {
        public static object Parse(string s)
        {
            int i = 0;
            var v = Value(s, ref i);
            Ws(s, ref i);
            if (i != s.Length) throw new FormatException("RT48Json：余分な文字（位置 " + i + "）");
            return v;
        }

        static void Ws(string s, ref int i) { while (i < s.Length && (s[i] == ' ' || s[i] == '\t' || s[i] == '\n' || s[i] == '\r' || s[i] == '﻿')) i++; }

        static bool Lit(string s, ref int i, string w)
        {
            if (string.CompareOrdinal(s, i, w, 0, w.Length) != 0) return false;
            i += w.Length; return true;
        }

        static object Value(string s, ref int i)
        {
            Ws(s, ref i);
            if (i >= s.Length) throw new FormatException("RT48Json：終わりが早い");
            char c = s[i];
            if (c == '{') return Obj(s, ref i);
            if (c == '[') return Arr(s, ref i);
            if (c == '"') return Str(s, ref i);
            if (Lit(s, ref i, "true")) return true;
            if (Lit(s, ref i, "false")) return false;
            if (Lit(s, ref i, "null")) return null;
            if (Lit(s, ref i, "NaN")) return double.NaN;
            if (Lit(s, ref i, "Infinity")) return double.PositiveInfinity;
            if (Lit(s, ref i, "-Infinity")) return double.NegativeInfinity;
            int a = i;
            while (i < s.Length && "+-0123456789.eE".IndexOf(s[i]) >= 0) i++;
            if (a == i) throw new FormatException("RT48Json：読めない文字 '" + c + "'（位置 " + i + "）");
            return double.Parse(s.Substring(a, i - a), NumberStyles.Float, CultureInfo.InvariantCulture);
        }

        static Dictionary<string, object> Obj(string s, ref int i)
        {
            var d = new Dictionary<string, object>();
            i++;
            Ws(s, ref i);
            if (s[i] == '}') { i++; return d; }
            while (true)
            {
                Ws(s, ref i);
                var k = Str(s, ref i);
                Ws(s, ref i);
                if (s[i] != ':') throw new FormatException("RT48Json：':' がない（位置 " + i + "）");
                i++;
                d[k] = Value(s, ref i);
                Ws(s, ref i);
                if (s[i] == ',') { i++; continue; }
                if (s[i] == '}') { i++; return d; }
                throw new FormatException("RT48Json：',' か '}' がない（位置 " + i + "）");
            }
        }

        static List<object> Arr(string s, ref int i)
        {
            var a = new List<object>();
            i++;
            Ws(s, ref i);
            if (s[i] == ']') { i++; return a; }
            while (true)
            {
                a.Add(Value(s, ref i));
                Ws(s, ref i);
                if (s[i] == ',') { i++; continue; }
                if (s[i] == ']') { i++; return a; }
                throw new FormatException("RT48Json：',' か ']' がない（位置 " + i + "）");
            }
        }

        static string Str(string s, ref int i)
        {
            if (s[i] != '"') throw new FormatException("RT48Json：文字の始めがない（位置 " + i + "）");
            i++;
            var sb = new StringBuilder();
            while (true)
            {
                char c = s[i++];
                if (c == '"') return sb.ToString();
                if (c != '\\') { sb.Append(c); continue; }
                char e = s[i++];
                switch (e)
                {
                    case '"': sb.Append('"'); break;
                    case '\\': sb.Append('\\'); break;
                    case '/': sb.Append('/'); break;
                    case 'b': sb.Append('\b'); break;
                    case 'f': sb.Append('\f'); break;
                    case 'n': sb.Append('\n'); break;
                    case 'r': sb.Append('\r'); break;
                    case 't': sb.Append('\t'); break;
                    case 'u': sb.Append((char)int.Parse(s.Substring(i, 4), NumberStyles.HexNumber, CultureInfo.InvariantCulture)); i += 4; break;
                    default: throw new FormatException("RT48Json：読めない \\" + e);
                }
            }
        }

        // ---------------------------------------------------------------- 取り出し
        public static Dictionary<string, object> O(object o) => o as Dictionary<string, object> ?? throw new FormatException("RT48Json：物ではない");
        public static List<object> A(object o) => o as List<object> ?? throw new FormatException("RT48Json：配列ではない");
        public static double D(object o) => o is double d ? d : o is bool b ? (b ? 1 : 0) : throw new FormatException("RT48Json：数ではない");
        public static int I(object o) => (int)Math.Round(D(o));
        public static string S(object o) => o as string ?? "";
        public static bool B(object o) => o is bool b ? b : o is double d && d != 0;
        public static object Get(Dictionary<string, object> d, string k) => d != null && d.TryGetValue(k, out var v) ? v : null;
        public static Dictionary<string, object> GetO(Dictionary<string, object> d, string k) => Get(d, k) as Dictionary<string, object>;
    }
}
