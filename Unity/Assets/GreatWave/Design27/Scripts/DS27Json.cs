using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text;

namespace GreatWave.Design27
{
    // 設計27：DS27 keypose パッケージの JSON（入れ子の配列 "origin": [[x, y, z], ...] を含む）を読むための小さな読み取り器。
    // JsonUtility は入れ子の配列と double を扱えないので、ここで読む。値は Dictionary<string, object>・List<object>・double・string・bool・null。
    public static class DS27Json
    {
        public static object Parse(string text)
        {
            int i = 0;
            var v = Value(text, ref i);
            Ws(text, ref i);
            if (i != text.Length) throw new FormatException("JSON の後ろに余分な文字があります（位置 " + i + "）。");
            return v;
        }

        static void Ws(string s, ref int i)
        {
            while (i < s.Length && (s[i] == ' ' || s[i] == '\t' || s[i] == '\n' || s[i] == '\r' || s[i] == '﻿')) i++;
        }

        static object Value(string s, ref int i)
        {
            Ws(s, ref i);
            if (i >= s.Length) throw new FormatException("JSON が途中で終わっています。");
            char c = s[i];
            if (c == '{') return Obj(s, ref i);
            if (c == '[') return Arr(s, ref i);
            if (c == '"') return Str(s, ref i);
            if (c == 't' && string.CompareOrdinal(s, i, "true", 0, 4) == 0) { i += 4; return true; }
            if (c == 'f' && string.CompareOrdinal(s, i, "false", 0, 5) == 0) { i += 5; return false; }
            if (c == 'n' && string.CompareOrdinal(s, i, "null", 0, 4) == 0) { i += 4; return null; }
            return Num(s, ref i);
        }

        static Dictionary<string, object> Obj(string s, ref int i)
        {
            var d = new Dictionary<string, object>();
            i++;
            Ws(s, ref i);
            if (i < s.Length && s[i] == '}') { i++; return d; }
            while (true)
            {
                Ws(s, ref i);
                var k = Str(s, ref i);
                Ws(s, ref i);
                if (i >= s.Length || s[i] != ':') throw new FormatException("JSON の ':' がありません（位置 " + i + "）。");
                i++;
                d[k] = Value(s, ref i);
                Ws(s, ref i);
                if (i < s.Length && s[i] == ',') { i++; continue; }
                if (i < s.Length && s[i] == '}') { i++; return d; }
                throw new FormatException("JSON のオブジェクトが閉じていません（位置 " + i + "）。");
            }
        }

        static List<object> Arr(string s, ref int i)
        {
            var l = new List<object>();
            i++;
            Ws(s, ref i);
            if (i < s.Length && s[i] == ']') { i++; return l; }
            while (true)
            {
                l.Add(Value(s, ref i));
                Ws(s, ref i);
                if (i < s.Length && s[i] == ',') { i++; continue; }
                if (i < s.Length && s[i] == ']') { i++; return l; }
                throw new FormatException("JSON の配列が閉じていません（位置 " + i + "）。");
            }
        }

        static string Str(string s, ref int i)
        {
            if (s[i] != '"') throw new FormatException("JSON の文字列ではありません（位置 " + i + "）。");
            i++;
            var sb = new StringBuilder();
            while (i < s.Length)
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
                    case 'u': sb.Append((char)Convert.ToInt32(s.Substring(i, 4), 16)); i += 4; break;
                    default: throw new FormatException("JSON の不明なエスケープ \\" + e);
                }
            }
            throw new FormatException("JSON の文字列が閉じていません。");
        }

        static double Num(string s, ref int i)
        {
            int st = i;
            while (i < s.Length && "+-0123456789.eE".IndexOf(s[i]) >= 0) i++;
            if (i == st) throw new FormatException("JSON の値が読めません（位置 " + i + "）。");
            return double.Parse(s.Substring(st, i - st), NumberStyles.Float, CultureInfo.InvariantCulture);
        }

        // ---- 取り出しの補助
        public static Dictionary<string, object> AsObj(object o, string what)
        {
            if (o is Dictionary<string, object> d) return d;
            throw new FormatException(what + " がオブジェクトではありません。");
        }

        public static object Get(Dictionary<string, object> d, string key)
        {
            if (!d.TryGetValue(key, out var v)) throw new FormatException("JSON に " + key + " がありません。");
            return v;
        }

        public static bool Has(Dictionary<string, object> d, string key) => d.ContainsKey(key) && d[key] != null;

        public static double Num(Dictionary<string, object> d, string key)
        {
            var v = Get(d, key);
            if (v is double x) return x;
            throw new FormatException(key + " が数ではありません。");
        }

        public static string Text(Dictionary<string, object> d, string key)
        {
            var v = Get(d, key);
            if (v is string x) return x;
            throw new FormatException(key + " が文字列ではありません。");
        }

        public static double[] Nums(object o, string what)
        {
            if (!(o is List<object> l)) throw new FormatException(what + " が配列ではありません。");
            var a = new double[l.Count];
            for (int k = 0; k < l.Count; k++)
            {
                if (!(l[k] is double x)) throw new FormatException(what + " の " + k + " 番目が数ではありません。");
                a[k] = x;
            }
            return a;
        }

        public static double[][] Nums2(object o, string what)
        {
            if (!(o is List<object> l)) throw new FormatException(what + " が配列ではありません。");
            var a = new double[l.Count][];
            for (int k = 0; k < l.Count; k++) a[k] = Nums(l[k], what + "[" + k + "]");
            return a;
        }
    }
}
