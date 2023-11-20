import datetime
import pandas as pd
import psycopg2
import streamlit as st
from streamlit import session_state as ss
from streamlit_extras.metric_cards import style_metric_cards
from streamlit_folium import folium_static
import folium
import webbrowser
from urllib.parse import quote


#########################################
################# INIT ##################
#########################################
# 페이지 기본 설정
st.set_page_config(
    page_title="마이냉장고",
    page_icon="😋",
    layout="centered",
    initial_sidebar_state="expanded",
    menu_items=None
)

# PostgreSQL 연결
@st.cache_resource # Uses st.cache_resource to only run once.
def init_connection():
    return psycopg2.connect(**st.secrets["postgres"])
conn = init_connection()


# OLAP Query 실행 함수
def run_query(query):
    with conn.cursor() as cur:
        cur.execute(query)
        return cur.fetchall()


# OLTP Query 실행 함수
def execute_query(query):
    with conn.cursor() as cur:
        cur.execute(query)
        conn.commit()


# Session state initialization
if 'today' not in ss:
    ss.today = datetime.datetime.now()
if 'buy_state' not in ss:
    ss.buy_state = False
if 'cart' not in ss:
    ss.cart = {'iid': [], '상품명': [], '수량':[]}
if 'buy_num' not in ss:
    ss.buy_num = 0
if 'text_input' not in ss:
    ss.text_input = ''
if 'push_buy' not in ss:
    ss.push_buy = False
if 'is_login' not in ss:
    ss.is_login = False
if 'item_search' not in ss:
    ss.item_search = False
if 'edit_ref' not in ss:
    ss.edit_ref = False
if 'del_ref' not in ss:
    ss.del_ref = False
if 'values' not in ss:
    ss.values = ''
if 'uid' not in ss:
    ss.uid = ''

def submit():
    ss.text_input = ss.widget
    ss.widget = ''




#########################################
################# PAGES #################
#########################################
# 로그인 페이지
def login():
    st.title('😋 마이냉장고 로그인')
    st.write('당신의 냉장고 관리를 편안하게~')
    st.markdown('---')
    uid = st.text_input('uid를 입력하세요 (아무거나 입력)', '')

    if uid != '':
        try:
            uid = int(uid)
        except:
            pass
    if uid == '':
        message_login = '게스트로 이용'
    else:
        ss.is_login = True
        ss.uid = uid #uid 저장

        q_user_info = f'''
            select uid, uname from users
            where users.uid = {ss.uid};
            '''
        users = run_query(q_user_info)
        if len(users) == 1:
            ss.uname = users[0][1]
            st.experimental_rerun()
        else: # 해당 uid 없음
            message_login = '올바르지 않은 uid'
            ss.is_login = False
    st.write(message_login)
    st.markdown('---')
    
# 사이드 바
def side_bar():
    with st.sidebar:
        st.title('😋 마이냉장고')
        st.write(f'{ss.uname}님의 냉장고 관리를 편안하게')
        st.markdown('---')
        page = st.radio('메뉴', ('냉장고', '쇼핑', '공동구매', '주문내역', '레시피'))
        st.markdown('---')

        # 날짜 변경
        st.markdown(f'''
                    오늘 날짜: {ss.today.year}년 {ss.today.month}월 {ss.today.day}일
                    ''')
        col_day1, col_day2 = st.columns(2)
        with col_day1:
            if st.button('1 Day Minus'):
                ss.today -= datetime.timedelta(days=1)
                st.experimental_rerun()
        with col_day2:
            if st.button('1 Day Plus'):
                ss.today += datetime.timedelta(days=1)
                st.experimental_rerun()
    return page

# 소비기한 임박 알림
def dur_alert():
    q_dur_alert = f'''
    select iname as name, (mdt + exp_dur) - '{ss.today}' as rdays
    from refrigerator
    join item using(iid)
    where uid = {ss.uid} and (mdt + exp_dur) - '{ss.today}' < 5 and auto = true
    union
    select c.c2name as name, (mdt + r2.exp_dur) - '{ss.today}' as rdays
    from refrigerator r2
    join item using(iid)
    join correct_category_2 c using(c2id)
    where uid = {ss.uid} and (mdt + r2.exp_dur) - '{ss.today}' < 5 and auto = false;
    '''
    rows = run_query(q_dur_alert)
    
    st.markdown('---')
    if len(rows) > 0:
        st.header('⏳ 소비기한이 얼마 남지 않았어요!')
        cols = st.columns(len(rows))
        for i, col in enumerate(cols):
            col.metric(label=str(i+1), value=rows[i][0], delta=rows[i][1])
        style_metric_cards()
    else:
        st.header('😎 냉장고의 모든 상품이 신선해요')
    st.markdown('---')

# 나의 냉장고 보기
def view_ref():
    st.header('🧳 나의 냉장고')
    
    category1 = ['과일', '채소', '정육/계란', '냉장/냉동/간편식','델리/샐러드',
             '통조림/즉석밥/면', '밀키트', '수산/건어물', '김치/반찬', '쌀/잡곡',
             '베이커리', '유아식', '장/양념/소스', '간식/떡/빙과', '커피/음료',
             '우유/유제품',  '건강식품', '생필품/꽃/반려동물', '선물세트']

    ## 음식 보여주기 드롭다운
    with st.expander("음식 보여주기 설정"):
        selected_category = st.multiselect('카테고리 선택', category1, category1)  # 선택지, 최초 선택

    ## 노트 보여주기 드롭다운
    q_show_note = '''
    select distinct note
    from refrigerator
    '''
    noteresults = run_query(q_show_note)
    notetags = [noteresult[0] for noteresult in noteresults]
    with st.expander("메모 설정"):
        selected_memo = st.multiselect('카테고리 선택', notetags, notetags)  # 선택지, 최초 선택

    ## 냉장고 보여주는 테이블
    q_show_my_ref = f'''
    select distinct f1.c1name, subq.name, subq.rdays, subq.pdt, subq.note, subq.iid
    from (
        select i1.iid, c21.c2name, i1.iname as name, (r1.mdt + r1.exp_dur) - '{ss.today}' as rdays, r1.pdt as pdt, r1.note as note
        FROM refrigerator r1
        JOIN item i1 USING(iid)
        JOIN correct_category_2 c21 USING(c2id)
        WHERE r1.uid = {ss.uid} and r1.auto = true
        UNION
        SELECT i2.iid, c.c2name, c.c2name, (r2.mdt + r2.exp_dur) - '{ss.today}' as rdays, r2.pdt, r2.note
        FROM refrigerator r2
        JOIN item i2 USING(iid)
        join correct_category_2 c USING(c2id)
        WHERE r2.uid = {ss.uid} and r2.auto = false)
        as subq
    left join correct_category_2 f2 on subq.c2name = f2.c2name  
    left join category_1 f1 on f2.c1id = f1.c1id  
    order by subq.pdt asc;
    '''
    rows = run_query(q_show_my_ref)

    if len(rows) > 0:
        rows = pd.DataFrame(rows)
        rows.columns = ["대분류", "이름", "남은 소비기간", "구매일자", "노트", 'iid']
        row = rows[["대분류", "이름", "남은 소비기간", "구매일자", "노트"]]
        if len(selected_category)>0 :
            dfrows = row[(row['대분류'].isin(selected_category))&(row['노트'].isin(selected_memo))]
        else:
            dfrows = row
        table = st.dataframe(dfrows, width=2000)

    else:
        st.subheader('😢 나의 냉장고가 비어있어요')

    with st.expander("수정하기"):
        col1, col2 = st.columns(2)
        with col1:
            row_index = st.selectbox("아이템 번호 선택", rows.index)
            # 선택한 재료 정보 표시
            selected_ingredient = dfrows.loc[row_index, '이름']
            selected_exp_date = dfrows.loc[row_index, '남은 소비기간']
            selected_memo = dfrows.loc[row_index, '노트']
            new_exp_date = st.number_input("유효기간 조정하기", value=selected_exp_date)
            selected_iid = rows.loc[row_index, 'iid']
        with col2:
            new_ingredient = st.text_input("이름", selected_ingredient)
            memo_input = st.text_area("메모 입력하기: '내일 먹을 것'", selected_memo)

            # 수정/삭제버튼
            update_button = st.button("수정하기")
            delete_button = st.button("마이 냉장고에서 제거")

            subcol1, subcol2 = st.columns(2)
            with subcol1:
                if update_button and ss.edit_ref == False:
                    q_apply_to_ref = f'''
                    update refrigerator
                    set note = '{memo_input}', exp_dur = '{ss.today}' - mdt + {new_exp_date} 
                    where uid = {ss.uid} and iid = {selected_iid}
                    '''
                    execute_query(q_apply_to_ref)
                    ss.edit_ref = True
                    st.experimental_rerun()
                elif ss.edit_ref == True:
                    st.write('수정완료')
                    ss.edit_ref = False

            with subcol2:
                if delete_button and ss.del_ref == False:
                    q_delete_to_ref = f'''
                    delete from refrigerator
                    where uid = {ss.uid} and iid = {selected_iid}
                    '''
                    execute_query(q_delete_to_ref)
                    ss.del_ref = True
                    st.experimental_rerun()
                elif ss.del_ref == True:
                    st.write('제거 완료')
                    ss.del_ref = False

# 수동으로 냉장고에 아이템 추가
def add_to_ref():
    item = st.text_input('<냉장고에 수동으로 아이템 이름을 입력하세요.>', '')
    if item != '' and ss.item_search == False:
        with st.form(key='my_form'):
            q_search_c2name = f'''
            select c2id, c2name
            from correct_category_2 
            where c2name like '%{item}%';
            '''
            rows = run_query(q_search_c2name)
            if len(rows)>0:
                c2ids = [r[0] for r in rows]
                c2names = [r[1] for r in rows]
            else:
                c2ids=[0]
                c2names = ['목록이 없습니다']
            option = st.selectbox('이 중 어떤 아이템인가요?', c2names)
            pdt = st.date_input('언제 구매하셨나요?', datetime.datetime.today())
            mdt = st.date_input('제조일자는 언제인가요?', datetime.datetime.today())
            submit_button = st.form_submit_button(label='등록')
            c2id = c2ids[c2names.index(option)]
        if mdt < datetime.date.today():
            q_insert_to_ref = f'''
            insert into refrigerator (uid, iid, pdt, mdt, auto, exp_dur)
            select {ss.uid} as uid, iid, '{pdt}' as pdt, '{mdt}' as mdt, false as auto, exp_dur
            from correct_category_2
            join item using(c2id)
            where c2id = {c2id}
            limit 1;            
            '''
            execute_query(q_insert_to_ref)
            ss.item_search = True
            st.experimental_rerun()
    elif item != '' and ss.item_search == True:
        st.write('아이템이 성공적으로 추가 되었습니다')
        ss.item_search = False

def shop(def_search='토마토'):
    st.markdown('''
    ## 쇼핑
    ''')

    ## 검색
    st.markdown('#### 검색')
    item_search = st.text_input('아이템 검색', def_search)
    query = f"select iid, iname, url from item where iname like '%{item_search}%'"
    rows = run_query(query)
    try: # 상품이 검색됨
        df = pd.DataFrame(rows)
        df.columns = ['iid', '상품명', 'url']

        hide_table_row_index = """
            <style>
            thead tr th:first-child {display:none}
            tbody th {display:none}
            </style>
            """
        hide_dataframe_row_index = """
            <style>
            .row_heading.level0 {display:none}
            .blank {display:none}
            </style>
            """

        # Inject CSS with Markdown
        st.markdown(hide_table_row_index, unsafe_allow_html=True)
        # Inject CSS with Markdown
        st.markdown(hide_dataframe_row_index, unsafe_allow_html=True)
        st.dataframe(df)
    except: # 검색 안됨
        '일치하는 상품이 없습니다.'
    
    ## 쇼핑
    cart_shop()

def cart_shop():
    st.markdown('#### 장바구니')
    st.text_input("iid로 장바구니 추가", key='widget', on_change=submit)
    if ss.text_input != '':
        try:
            # int로 변환되지 않는 input이 들어오면 오류 발생
            iid = int(ss.text_input)
            # 검색결과가 없으면 '[0][0]' 에서 오류가 발생함
            iname = run_query(f'select iname from item where iid = {iid}')[0][0]
            if iname != '':
                ss.cart['iid'].append(iid)
                ss.cart['상품명'].append(iname)
                ss.cart['수량'].append(1)
        except:
            '올바른 iid가 아닙니다.'
    else:
        pass
    ss.text_input = ''
    st.table(pd.DataFrame(ss.cart))

    col1, col2 = st.columns(2)
    with col1:
        if st.button('최하단 상품 수량 +1'):
            ss.cart['수량'][-1] += 1
            st.experimental_rerun()
    with col2:
        if st.button('최하단 상품 수량 -1'):
            ss.cart['수량'][-1] += 1
            st.experimental_rerun()


    if st.button('장바구니 초기화'):
        ss.cart = {'iid': [], '상품명': [], '수량':[]}
        ss.buy_num = 0
        st.experimental_rerun()

    if st.button('구매'):
        ss.push_buy = True
        ss.buy_num = len(ss.cart['iid'])

        iids = ss.cart['iid']
        cnts = ss.cart['수량']

        vals = ''

        for i in range(len(ss.cart['iid'])):
            vals += f'({iids[i]}, {cnts[i]}), '
        vals = vals[:-2]
        st.write(vals)
        pdt = datetime.datetime.now()
        st.write(pdt)

        ####### plist, phistory 를 update
        query = f'''
        WITH new_order AS (
        INSERT INTO phistory (uid, pdt)
        VALUES ({ss.uid}, '{pdt}')
        RETURNING pid, uid, pdt
        ), new_order_list AS (
        INSERT INTO plist
        SELECT new_order.pid, vals.iid, vals.cnt
        FROM new_order
        CROSS JOIN (
            VALUES {vals}
        ) AS vals(iid, cnt)
        RETURNING iid, cnt
        ), new_items_to_ref AS (
            SELECT iid, min(exp_dur) as exp_dur, min(mdt) as mdt
            FROM new_order_list
                join item using(iid)
                join correct_category_2 using(c2id)
                join inventory using(iid)
            where need_ref is true
            group by iid
        )
        insert into refrigerator (uid, iid, pdt, mdt, auto, exp_dur)
        select uid, iid, pdt, mdt, true, exp_dur
        from new_order
            cross join new_items_to_ref
            ;
        '''
        execute_query(query)

        ss.cart = {'iid': [], '상품명': [], '수량':[]}
        st.experimental_rerun()
 
    if ss.push_buy == True:
        st.write(ss.buy_num, "개의 제품을 구매하였습니다.")
        ss.push_buy = False    

def history():
    st.markdown('##  주문내역')
    q = f'''select ph.pid, ph.pdt, it.iname, pl.cnt from phistory ph
            join plist pl on ph.pid = pl.pid
            join item it on it.iid = pl.iid
            where uid = {ss.uid}
            order by pdt desc
            '''
    rows = run_query(q)
    df = pd.DataFrame(rows, columns=['구매고유번호', '구매시간', '상품명', '개수'])
    df

def recommend():
    rows = run_query(f"""
    select *
    from (SELECT rm.rid, r.rname, r.rtype, r.rcal, c2.c2name, r.rdetail, r."imageURL", c2.c2id, COUNT(rm.c2id) AS overlap, SUM(ri.urgentState) AS urgentCnt
	    FROM correct_rmaterial rm
	    JOIN (SELECT rf.iid, rd.c2id, CASE WHEN rd.rdays < 5 THEN 1 ELSE 0 END AS urgentState
	        FROM refrigerator rf
	        JOIN (select iid, i.c2id, (mdt + exp_dur) - current_date as rdays 
	            from refrigerator
	            join item using(iid)
	            join item i using (iid)
	            where uid = {ss.uid} and (mdt + exp_dur) - current_date < 5) rd 
	        ON rf.iid = rd.iid) ri
	    ON rm.c2id = ri.c2id
	    join recipe r on rm.rid = r.rid
	    join correct_category_2 c2 on rm.c2id = c2.c2id
	    GROUP BY rm.rid, r.rname, r.rtype, r.rcal, c2.c2name, r.rdetail, r."imageURL", c2.c2id
	    ORDER BY urgentCnt, overlap desc Limit 10 ) sub
    order by rid""")

    rows2 = run_query(f"""
    SELECT sub.rid, STRING_AGG(c2.c2name, ', ') AS concatenated_c2names
    FROM (
        SELECT rm.rid, rm.c2id,  ROW_NUMBER() OVER (PARTITION BY rm.rid ORDER BY urgentCnt, overlap DESC) AS row_num
        FROM correct_rmaterial rm
        right JOIN (
            SELECT rm.rid, r.rname, r.rtype, r.rcal, c2.c2name, r.rdetail, r."imageURL", c2.c2id, COUNT(rm.c2id) AS overlap, SUM(ri.urgentState) AS urgentCnt
            FROM correct_rmaterial rm
            JOIN (SELECT rf.iid, rd.c2id, CASE WHEN rd.rdays < 5 THEN 1 ELSE 0 END AS urgentState
                FROM refrigerator rf
                JOIN (select iid, i.c2id, (mdt + exp_dur) - current_date as rdays 
                    from refrigerator
                    join item using(iid)
                    join item i using (iid)
                    where uid = {ss.uid} and (mdt + exp_dur) - current_date < 5) rd 
                ON rf.iid = rd.iid) ri
            ON rm.c2id = ri.c2id
            join recipe r on rm.rid = r.rid
            join correct_category_2 c2 on rm.c2id = c2.c2id
            GROUP BY rm.rid, r.rname, r.rtype, r.rcal, c2.c2name, r.rdetail, r."imageURL", c2.c2id
            ORDER BY urgentCnt, overlap DESC
            Limit 10
        ) rows ON rm.rid = rows.rid
        WHERE rm.c2id != rows.c2id
         order by rm.rid
    ) sub 
    JOIN correct_category_2 c2
    ON sub.c2id = c2.c2id
    WHERE sub.row_num <= 2
    GROUP BY sub.rid""")

    # 페이지 헤더, 서브헤더 제목 설정
    st.header("레시피 추천")
    st.subheader("냉장고 속 재료를 활용하여 요리해 보세요")

    df = pd.DataFrame(rows)
    data = df.iloc[:,1:5]  # 열 인덱스 슬라이싱 수정

    df2 = pd.DataFrame(rows2)
    data2 = df2.iloc[:,1]  # 열 인덱스 슬라이싱 수정

    data.columns = ['요리이름', '요리종류', '칼로리', '활용가능 식재료']
    st.dataframe(data, use_container_width=True)

    st.markdown("<h3 style='text-align:left;'>원하는 요리를 선택해 주세요</h3>", unsafe_allow_html=True)
    option = st.selectbox(
        'select',
        (df.iloc[0, 1], df.iloc[1, 1], df.iloc[2, 1], df.iloc[3, 1], df.iloc[4, 1], df.iloc[5, 1], df.iloc[6, 1], df.iloc[7, 1], df.iloc[8, 1], df.iloc[9, 1])
    )  # 옵션 값 수정
    st.markdown("<h3 style='text-align:left;'>요리 상세 정보</h3>", unsafe_allow_html=True)
    st.write('You selected:', option)   

    for i in range(len(df)):
        if df.iloc[i, 1] == option:
            rec_name = df.iloc[i, 1]
            rec_type = df.iloc[i, 2]
            rec_cal = df.iloc[i, 3]
            rec_detail = df.iloc[i, 5]
            rec_image = df.iloc[i, 6]
            rec_plusMaterial = df2.iloc[i,1]
            break 
        st.markdown("""
    <style>
        table {
            width: 100%;
            text-align: center;
        }
        th, td {
            text-align: center;
        }
    </style>
    """, unsafe_allow_html=True)

    data = [
        ['요리명', rec_name],
        ['종류', rec_type],
        ['칼로리', rec_cal],
        ['조리법', rec_detail],
        ['추가 필요 식재료', rec_plusMaterial],
    
    ]
    
    st.image(rec_image)
    for row in data:
        st.markdown(f"| {row[0]} |  :  \n {row[1]} ")

    # # 검색어
    # search_query = rec_plusMaterial

    # # 검색어 URL 인코딩
    # encoded_query = quote(search_query)

    # # 쿠팡 검색 결과 페이지 URL
    # url = f"https://www.coupang.com/np/search?component=&q={encoded_query}"

    # # 버튼 클릭 여부 확인
    # if st.button("부족한 식재료 사러가기"):
    # # 새 창으로 URL 열기
    #    webbrowser.open_new_tab(url)

    with st.expander('쇼핑'):
        shop(rec_plusMaterial.split()[0].strip(','))


def co_buying_table():
    q_co_buying = f'''
    SELECT c.c2name, i.iname, u2.uname
    FROM users u1
    JOIN users u2 ON u1.uid <> u2.uid
    JOIN cart c1 ON u1.uid = c1.uid
    JOIN cart c2 ON u2.uid = c2.uid
    JOIN item i ON c1.iid = i.iid
    JOIN correct_category_2 c USING(c2id)
    WHERE u1.uid = {ss.uid}
    AND c1.iid = c2.iid
    AND ST_DistanceSphere(ST_MakePoint(u1.long, u1.lat),
    ST_MakePoint(u2.long, u2.lat))<=2000
    ORDER BY ST_DistanceSphere(ST_MakePoint(u1.long, u1.lat), ST_MakePoint(u2.long, u2.lat)) ASC
    '''
    rows = run_query(q_co_buying)

    st.markdown("""---""")
    st.markdown('## 공동구매')
    st.markdown("""---""")

    rows_df = pd.DataFrame(rows, columns = ["상품", "상세 설명", "공동구매 희망자"])
    rows_df["구매"] = False
    columns = ["구매"]+list(rows_df.columns[:-1])
    rows_df["공동구매 희망자"] = rows_df["공동구매 희망자"].str.slice(stop=-1) + "*"
    rows_df = rows_df[columns]

    column_config = {
        "구매": st.column_config.CheckboxColumn(
            "구매",
            default=False
        )
    }

    main_checkbox = st.checkbox('전체 상품: %s개' % len(rows))
    st.markdown("""---""")

    if main_checkbox:
        rows_df['구매'] = True  

    st.data_editor(
        rows_df,
        width = 700,
        column_config=column_config,
        disabled=[],
        hide_index=True
    )

#구매를 누르면 메세지 팝업창이 뜨지만 '나가기'버튼이 활성화 되어있지 않아 나가기가 안됩니다.
#시현때 먼저 페이지 전체를 보여주고 만약 구매 메세지를 보내고 싶으면 구매 checkbox클릭해서 
# 구매 누르면 message box뜨는거 까지 보여주는 순서로 가야할 것 같습니다. 

    col1, col2, col3, col4, col5 = st.columns([1, 1, 1, 1, 1])
    with col5:
        if st.button("구매"):
            st.markdown(
                """
                <style>
                .popup {
                    position: fixed;
                    top: 50%;
                    left: 50%;
                    transform: translate(-50%, -50%);
                    background-color: white;
                    padding: 20px;
                    border: 1px solid #ccc;
                    border-radius: 5px;
                    z-index: 9999;
                }
                </style>
                """
                , unsafe_allow_html=True
            )

            st.markdown(
                """
                <div class="popup-wrapper">
                    <div class="popup">
                        <h2>같이 공동구매해요~</h2>
                        <p>공동구매 희망자에게 메세지를 보내세요!</p>
                        <button id="closeButton">나가기</button>
                    </div>
                </div>

                <script>
                const closeButton = document.getElementById('closeButton');
                closeButton.addEventListener('click', closePopup);
                function closePopup() {
                    const popupWrapper = document.querySelector('.popup-wrapper');
                    popupWrapper.style.display = 'none';
                }
                </script>
                """
                , unsafe_allow_html=True
            )

    st.markdown("""---""")

def co_buying_map():
    #display on map
    q_get_lat_lon = f'''
    SELECT u2.lat, u2.long, u2.uname
    FROM users u1
    JOIN users u2 ON u1.uid <> u2.uid
    JOIN cart c1 ON u1.uid = c1.uid
    JOIN cart c2 ON u2.uid = c2.uid
    WHERE u1.uid = {ss.uid}
    AND c1.iid = c2.iid
    AND ST_DistanceSphere(ST_MakePoint(u1.long, u1.lat),
    ST_MakePoint(u2.long, u2.lat))<=2000
    ORDER BY ST_DistanceSphere(ST_MakePoint(u1.long, u1.lat), ST_MakePoint(u2.long, u2.lat)) ASC
    '''
    q_get_me = f'''
    SELECT distinct(u1.uname), u1.lat, u1.long
    FROM users u1
    JOIN users u2 ON u1.uid <> u2.uid
    JOIN cart c1 ON u1.uid = c1.uid
    JOIN cart c2 ON u2.uid = c2.uid
    WHERE u1.uid = {ss.uid}
    AND c1.iid = c2.iid
    AND ST_DistanceSphere(ST_MakePoint(u1.long, u1.lat),
    ST_MakePoint(u2.long, u2.lat))<=2000
    '''

    cursor = conn.cursor()
    cursor1 = conn.cursor()
    cursor.execute(q_get_lat_lon)
    cursor1.execute(q_get_me)
    results = cursor.fetchall()
    results1 = cursor1.fetchall()

    data = []
    for row in results:
        lat = row[0]
        lon = row[1]
        name = row[2]
        row_dict = {"latitude":lat, "longitude": lon, "name": name}
        data.append(row_dict)
    places = pd.DataFrame(data)

    data_me = []
    for row in results1:
        my_name = row[0]
        my_lat = row[1]
        my_long = row[2]
        row_dict = {"my_name":my_name, "my_lat":my_lat, "my_long":my_long}
        data_me.append(row_dict)
    my_name = pd.DataFrame(data_me)

    center_lat, center_lon = places.iloc[0]['latitude'], places.iloc[0]['longitude']
    m = folium.Map(location=[center_lat, center_lon], zoom_start=13)
    folium.TileLayer('CartoDB Positron').add_to(m)

    for i, place in places.iterrows():
        lat = place['latitude']
        lon = place['longitude']
        name = place['name']
        truncated_name = name[:2] + '*'

        html_content = '''
        <div style="
            font-size: 12pt;
            color: black;
            text-shadow:
                -1px -1px 2px white,
                1px -1px 2px white,
                -1px 1px 2px white,
                1px 1px 2px white;
            ">
            <strong>{}</strong>
        </div>'''.format(truncated_name)
        
        folium.Marker(location=[lat, lon], 
                    zoom_start=12,
                    tooltip=name, 
                    icon = folium.DivIcon(icon_size = (150, 36),
                                          icon_anchor=(75,18), 
                                          html=html_content),
                    ).add_to(m)
        
        folium.Marker(location = [lat, lon],).add_to(m)

        folium.Circle(
            location=[lat, lon],
            radius=2000,
            fill=True,
            fill_color='blue',
            fill_opacity=0.1
        ).add_to(m)

    
    for i, me in my_name.iterrows():
        my_name = me["my_name"]
        my_lat = me["my_lat"]
        my_long = me["my_long"]
        icon = folium.Icon(color = 'green', icon = "smile", prefix="fa")
        folium.Marker(location = [my_lat, my_long], 
                      icon=icon).add_to(m)
    
        html_content = '''
        <div style="
            font-size: 12pt;
            color: black;
            text-shadow:
                -1px -1px 2px white,
                1px -1px 2px white,
                -1px 1px 2px white,
                1px 1px 2px white;
            ">
            <strong>{}</strong>
        </div>'''.format(my_name)
        
        folium.Marker(location=[lat, lon], 
                    zoom_start=12,
                    tooltip=name, 
                    icon = folium.DivIcon(icon_size = (150, 36),
                                            icon_anchor=(75,18), 
                                            html=html_content),
                    ).add_to(m)   

    folium_static(m)


#########################################
################# MAIN ##################
#########################################
if ss.is_login == False:
    login()
else:
    page = side_bar()
    if page == '냉장고':
        dur_alert()
        view_ref()
        add_to_ref()
    elif page == '쇼핑':
        shop()
    elif page == '공동구매':
        co_buying_table()
        co_buying_map()  
    elif page == '주문내역':
        history()
    elif page == '레시피':
        recommend()