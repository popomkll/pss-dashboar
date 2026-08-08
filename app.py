def login_with_email(email, password):
    """POSTリクエストで公式ログインAPIにアクセスしてトークンを取得"""
    # ログイン用主要エンドポイント
    url = "https://api.pixelstarships.com/UserService/EmailPasswordLogin"

    # POST送信用のフォームデータ構造
    payload = {
        "email": email,
        "password": password,
        "deviceType": "DeviceTypeAndroid",
    }

    try:
        # POST リクエスト（data=payload）で送信
        res = requests.post(url, data=payload, headers=HEADERS, timeout=10)

        # もしPOSTでダメな場合、フォールバックでGETも試行
        if res.status_code == 404:
            res = requests.get(url, params=payload, headers=HEADERS, timeout=10)

        if res.status_code == 200:
            root = ET.fromstring(res.content)

            # XML全体から accessToken 属性を全検索
            token = None
            for elem in root.iter():
                token = elem.attrib.get("accessToken") or elem.attrib.get("AccessToken")
                if token:
                    break

            if token:
                return token, "✅ ログイン成功！"

            # 認証エラーメッセージの取得
            error_msg = (
                root.attrib.get("errorMessage")
                or root.attrib.get("error")
                or "認証失敗: アカウント情報をご確認ください"
            )
            return None, f"❌ {error_msg}"
        else:
            return None, f"❌ 通信エラー (HTTP {res.status_code})"

    except Exception as e:
        return None, f"❌ 例外発生: {e}"