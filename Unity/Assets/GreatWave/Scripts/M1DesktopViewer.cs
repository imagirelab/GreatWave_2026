using System;
using UnityEngine;
using UnityEngine.InputSystem;

namespace GreatWave
{
    public class M1DesktopViewer : MonoBehaviour
    {
        [Serializable] public class View
        {
            public string label;
            public Vector3 position, target;
            public float fieldOfView = 60, orthographicSize = 37;
            public bool orthographic;
        }
        public Camera viewCamera;
        public View[] views;
        public GameObject mapOverlay;
        public bool recording;
        public bool compactRevisionLayout;
        [NonSerialized] public Keyboard testKeyboard;
        public int CurrentView { get; private set; }
        public bool Paused { get; private set; }
        Font font;
        GUIStyle style;
        Vector2 look;
        Quaternion baseRotation;

        void Start()
        {
            font = Font.CreateDynamicFontFromOSFont(new[] { "Yu Gothic", "Meiryo", "Microsoft YaHei UI", "MS Gothic" }, 24);
            SelectView(0);
            Debug.Log("M1_DESKTOP_START: static composition; fluid/HMD unverified");
        }

        void Update()
        {
            if (recording) return;
            var keyboard = testKeyboard ?? Keyboard.current;
            if (keyboard != null)
            {
                if (keyboard.qKey.wasPressedThisFrame) Application.Quit();
                if (keyboard.digit1Key.wasPressedThisFrame) SelectView(0);
                if (keyboard.digit2Key.wasPressedThisFrame) SelectView(1);
                if (keyboard.digit3Key.wasPressedThisFrame) SelectView(2);
                if (keyboard.digit4Key.wasPressedThisFrame) SelectView(3);
                if (keyboard.digit5Key.wasPressedThisFrame && views.Length > 4) SelectView(4);
                if (keyboard.rKey.wasPressedThisFrame) SelectView(CurrentView);
                if (keyboard.spaceKey.wasPressedThisFrame) Paused = !Paused;
                if (keyboard.escapeKey.wasPressedThisFrame) Paused = true;
                ApplyLook(new Vector2((keyboard.rightArrowKey.isPressed ? 1 : 0) - (keyboard.leftArrowKey.isPressed ? 1 : 0),
                    (keyboard.downArrowKey.isPressed ? 1 : 0) - (keyboard.upArrowKey.isPressed ? 1 : 0)) * (45 * Time.unscaledDeltaTime));
            }
            if (testKeyboard == null && Mouse.current != null && Mouse.current.rightButton.isPressed)
            { var delta = Mouse.current.delta.ReadValue(); ApplyLook(new Vector2(delta.x,-delta.y) * .12f); }
        }

        public void SelectView(int index)
        {
            if (index < 0 || index >= views.Length) throw new ArgumentOutOfRangeException(nameof(index));
            CurrentView = index;
            var view = views[index];
            viewCamera.orthographic = view.orthographic;
            viewCamera.orthographicSize = view.orthographicSize;
            viewCamera.fieldOfView = view.fieldOfView;
            viewCamera.aspect = 1280f / 720;
            viewCamera.transform.position = view.position;
            viewCamera.transform.LookAt(view.target, view.orthographic ? Vector3.forward : Vector3.up);
            baseRotation = viewCamera.transform.rotation;
            look = Vector2.zero; Paused = false;
            if (mapOverlay != null) mapOverlay.SetActive(index == 4);
        }

        public void ApplyLook(Vector2 degrees)
        {
            if (Paused || recording || views[CurrentView].orthographic) return;
            look.x = Mathf.Clamp(look.x + degrees.x,-100,100);
            look.y = Mathf.Clamp(look.y + degrees.y,-65,65);
            viewCamera.transform.rotation = baseRotation * Quaternion.Euler(look.y,look.x,0);
        }

        void OnGUI()
        {
            if (recording) return;
            if (style == null) { style = new GUIStyle(GUI.skin.label) { font = font, fontSize = 18 }; style.normal.textColor = new Color(.97f,.95f,.88f); }
            var scale = Screen.width / 1280f;
            GUI.matrix = Matrix4x4.Scale(new Vector3(scale,scale,1));
            float height = Screen.height / scale;
            if (compactRevisionLayout)
            {
                style.fontSize=15;
                GUI.color=new Color(.035f,.09f,.14f,.95f);GUI.DrawTexture(new Rect(844,12,420,134),Texture2D.whiteTexture);GUI.color=Color.white;
                GUI.Label(new Rect(860,22,394,28),"15 修正01 / "+views[CurrentView].label,style);
                GUI.Label(new Rect(860,50,394,24),"静止模型 / 流体・HMD未検証",style);
                GUI.Label(new Rect(860,76,394,24),"1 比較　2 船上　3 側面　4 背面　5 範囲",style);
                GUI.Label(new Rect(860,100,394,36),"右ドラッグ・矢印 / R 戻る / Space 停止 / Q 終了",style);
                return;
            }
            GUI.color = new Color(.035f,.09f,.14f,.95f);
            GUI.DrawTexture(new Rect(16,height-82,1248,68),Texture2D.whiteTexture);
            GUI.color = Color.white;
            GUI.Label(new Rect(32,height-77,1210,30),"M1 静止構図 / 流体未検証 / HMD未検証　　" + views[CurrentView].label + (Paused ? "・停止中" : ""),style);
            GUI.Label(new Rect(32,height-46,1210,30),"1 比較　2 船上　3 側面　4 背面　5 範囲図　右ドラッグ・矢印 見回し　R 戻す　Space 停止　Q 終了",style);
        }
    }
}
