#!/usr/bin/env python
# coding: utf-8

# In[6]:


# ECM Grib2 FAX天気図　FXFE5782 / FXFE5784の　700hPa湿数、500hPa気温予想図
#
#           2023/07/25 Ryuta Kurora
#
import math
import pygrib
import xarray as xr
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import matplotlib.path as mpath
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import datetime
import sys
#
import metpy.calc as mpcalc
from metpy.units import units
from scipy.ndimage import maximum_filter, minimum_filter
#
#import argparse


# In[2]:


# ECM GRIB2の読み込む初期値の年月日時をUTCで与えます。
i_year =2023
i_month = 5
i_day = 23
i_hourZ = 18
#
# ECMWF GRIB2の読み込む初期値の年月日時をUTCで指定する。
i_ft = 0
#
# 読み込む気圧面の気圧
tagTmp=500
tagTTd=700
#
## GPVの切り出し領域の指定：(lonW,latS)-(lonE,latN)の矩形                                                                                                      
latS=-20
latN=80
lonW=70
lonE=190
#
# 描画する範囲の大まかな指定
## 描画指定
# 基準の経度  JAPAN:140 USA:270
set_central_longitude=140
flag_border=False
# 地図の描画範囲指定
n_area=0
if n_area == 0:
    i_area = [108, 156, 17, 55]  #FEAX 極東                                                                   
    str_area = ""
elif n_area == 1:
    i_area = [115, 151, 20, 50]  #fx85 日本付近                                                               
    str_area = "_j"
elif n_area == 2:
    i_area = [105,180,0,65]      #ASAS                                                                        
    str_area = "_a"
elif n_area == 9:
    set_central_longitude=270
    i_area = [238, 286, 17, 55]  # USA
    str_area = "_usa"
    lonW=210  # JAPAN 70
    lonE=330  # JAPAN 190
    flag_border=True
else:
    i_area = [108, 156, 17, 55]  #FEAX 極東                                                                   
    str_area = ""
#
# 緯線・経線の指定
dlon,dlat=10,10   # 10度ごとに
## 気温　等値線
levels_tmp =np.arange(-60,42,3)
levels_tmp1  =np.arange(-60, 42, 15) # 等値線 太線  
## 露点差 ハッチ 
levels_h_ttd=[0, 3, 6, 18, 100]
levels_h_ttd_col=['green','0.4','1.0','yellow']
## 露点差 等値線
levels_ttd=np.arange(3,30,3)
#
# GRIB2データファイルの格納先フォルダー名
data_fld="./data/ecm/"


# In[3]:


## 緯度経度で指定したポイントの図上の座標などを取得する関数 transform_lonlat_to_figure() 
# 図法の座標 => pixel座標 => 図の座標　と3回の変換を行う
#  　pixel座標: plt.figureで指定した大きさxDPIに合わせ、左下を原点とするpixelで測った座標   
#  　図の座標: axesで指定した範囲を(0,1)x(0,1)とする座標
# 3つの座標を出力する
#    図の座標, Pixel座標, 図法の座標
def transform_lonlat_to_figure(lonlat, ax, proj):
    # lonlat:経度と緯度  (lon, lat) 
    # ax: Axes図の座標系    ex. fig.add_subplot()の戻り値
    # proj: axで指定した図法 
    #
    # 例 緯度経度をpointで与え、ステレオ図法る場合
    #    point = (140.0,35.0)
    #    proj= ccrs.Stereographic(central_latitude=60, central_longitude=140) 
    #    fig = plt.figure(figsize=(20,16))
    #    ax = fig.add_subplot(1, 1, 1, projection=proj)
    #    ax.set_extent([108, 156, 17, 55], ccrs.PlateCarree())
    #
    ## 図法の変換
    # 参照  https://scitools.org.uk/cartopy/docs/v0.14/crs/index.html                    
    point_proj = proj.transform_point(*lonlat, ccrs.PlateCarree())
    #
    # pixel座標へ変換
    # 参照　https://matplotlib.org/stable/tutorials/advanced/transforms_tutorial.html
    point_pix = ax.transData.transform(point_proj)
    #
    # 図の座標へ変換                                                           
    point_fig = ax.transAxes.inverted().transform(point_pix)
    return point_fig, point_pix, point_proj


# In[4]:


## 極大/極小ピーク検出関数                                                             
def detect_peaks(image, filter_size=3, dist_cut=5.0, flag=0):
    # filter_size: この値xこの値 の範囲内の最大値のピークを検出                        
    # dist_cut: この距離内のピークは1つにまとめる                                      
    # flag:  0:maximum検出  0以外:minimum検出                                          
    if flag==0:
      local_max = maximum_filter(image,
            footprint=np.ones((filter_size, filter_size)), mode='constant')
      detected_peaks = np.ma.array(image, mask=~(image == local_max))
    else:
      local_min = minimum_filter(image,
            footprint=np.ones((filter_size, filter_size)), mode='constant')
      detected_peaks = np.ma.array(image, mask=~(image == local_min))
    peaks_index = np.where((detected_peaks.mask != True))
    # peak間の距離行例を求める                                                         
    (x,y) = peaks_index
    size=y.size
    dist=np.full((y.size, y.size), -1.0)
    for i in range(size):
      for j in range(size):
        if i == j:
          dist[i][j]=0.0
        elif i>j:
          d = math.sqrt(((y[i] - y[j])*(y[i] - y[j]))
                        +((x[i] - x[j])*(x[i] - x[j])))
          dist[i][j]= d
          dist[j][i]= d
    # 距離がdist_cut内のpeaksの距離の和と、そのピーク番号を取得する 
    Kinrin=[]
    dSum=[]
    for i in range(size):
      tmpA=[]
      distSum=0.0
      for j in range(size):
        if dist[i][j] < dist_cut and dist[i][j] > 0.0:
          tmpA.append(j)
          distSum=distSum+dist[i][j]
      dSum.append(distSum)
      Kinrin.append(tmpA)
    # Peakから外すPeak番号を求める.  peak間の距離和が最も小さいものを残す              
    cutPoint=[]
    for i in range(size):
      val = dSum[i]
      val_i=image[x[i]][y[i]]
      for k in Kinrin[i]:
        val_k=image[x[k]][y[k]]
        if flag==0 and val_i < val_k:
            cutPoint.append(i)
            break
        if flag!=0 and val_i > val_k:
            cutPoint.append(i)
            break
        if val > dSum[k]:
            cutPoint.append(i)
            break
        if val == dSum[k] and i > k:
            cutPoint.append(i)
            break
    # 戻り値用に外すpeak番号を配列から削除                                             
    newx=[]
    newy=[]
    for i in range(size):
      if (i in cutPoint):
        continue
      newx.append(x[i])
      newy.append(y[i])
    peaks_index=(np.array(newx),np.array(newy))
    return peaks_index


# In[5]:


# 読み込むGRIB2形式ECMWFのファイル名
#  ex.  20230520120000-12h-oper-fc.grib2
if i_hourZ==0 or i_hourZ==12:
    ecm_fn_t="{0:4d}{1:02d}{2:02d}{3:02d}0000-{4:d}h-oper-fc.grib2"
else:
    ecm_fn_t="{0:4d}{1:02d}{2:02d}{3:02d}0000-{4:d}h-scda-fc.grib2"
ecm_fn= ecm_fn_t.format(i_year,i_month,i_day,i_hourZ,i_ft)
#
# データOpen
grbs = pygrib.open(data_fld + ecm_fn)
#
# データ取得
grbTm500 = grbs(shortName="t",typeOfLevel='isobaricInhPa',level=tagTmp)[0]
grbTm700 = grbs(shortName="t",typeOfLevel='isobaricInhPa',level=tagTTd)[0]
grbRh700 = grbs(shortName="r",typeOfLevel='isobaricInhPa',level=tagTTd)[0]
#
# データClose
grbs.close()
print("読み込んだファイル:",ecm_fn)
#
## データ切り出し                                                                                                                   
valT5, latT5, lonT5 = grbTm500.data(lat1=latS,lat2=latN,lon1=lonW,lon2=lonE)
valT7, latT7, lonT7 = grbTm700.data(lat1=latS,lat2=latN,lon1=lonW,lon2=lonE)
valR7, latR7, lonR7 = grbRh700.data(lat1=latS,lat2=latN,lon1=lonW,lon2=lonE)


# In[7]:


## Tを表示するための、xarrayデータセットを作成                                                                                   
dst = xr.Dataset(
    {
        "temperature": (["lat", "lon"],valT5 * units('K')),
    },
    coords={
        "level": [tagTmp],
        "lat": latT5[:,0],
        "lon": lonT5[0,:],
        "time": [grbTm500.validDate],
    },
)
# 単位
dst['temperature'].attrs['units'] = 'K'
dst['level'].attrs['units'] = 'hPa'
dst['lat'].attrs['units'] = 'degrees_north'
dst['lon'].attrs['units'] = 'degrees_east'
#
# metpy仕様に変換
dstp= dst.metpy.parse_cf()


# In[8]:


## T-Tdを算出されるための、xarrayデータセットを作成                                                                                   
ds = xr.Dataset(
    {
        "temperature": (["lat", "lon"],valT7 * units('K')),
        "relative_humidity": (["lat", "lon"],valR7 * units('%')),
    },
    coords={
        "level": [tagTTd],
        "lat": latT7[:,0],
        "lon": lonT7[0,:],
        "time": [grbTm700.validDate],
    },
)
# 単位
ds['temperature'].attrs['units'] = 'K'
ds['relative_humidity'].attrs['units']='%'
ds['level'].attrs['units'] = 'hPa'
ds['lat'].attrs['units'] = 'degrees_north'
ds['lon'].attrs['units'] = 'degrees_east'
#
## T-Tdの算出                                                                                                                                           
ds['ttd'] = ds['temperature'] - mpcalc.dewpoint_from_relative_humidity(ds['temperature'],ds['relative_humidity'])
ds['ttd'].attrs['units']='K'
#
dsp= ds.metpy.parse_cf()


# In[9]:


## タイトル文字列用
# 予想時間を得る
ft_hours=int(i_ft/100) * 24 + int(i_ft%100)
# 初期時刻の文字列
dt_i = grbTm500.analDate
dt_str = (dt_i.strftime("%H00UTC%d%b%Y")).upper()
dt_str2 = dt_i.strftime("%Y%m%d%H")


# In[10]:


### 境界データ作成
# Make state boundaries feature
states_provinces = cfeature.NaturalEarthFeature(category='cultural',
                                                name='admin_1_states_provinces_lines',
                                                scale='50m', facecolor='none')
# Make country borders feature
country_borders = cfeature.NaturalEarthFeature(category='cultural',
                                               name='admin_0_countries',
                                               scale='50m', facecolor='none')
#
## 図法指定                                                                             
proj = ccrs.Stereographic(central_latitude=60, central_longitude=set_central_longitude)
latlon_proj = ccrs.PlateCarree()
## 図のSIZE指定inch                                                                        
fig = plt.figure(figsize=(10,8))                                         
## 余白設定                                                                      
plt.subplots_adjust(left=0, right=1, bottom=0.06, top=0.98)
## 図に関する設定                                                                
plt.rcParams["contour.negative_linestyle"] = 'solid'
## 余白  FAX図に合わせる                                                         
ax = fig.add_subplot(1, 1, 1, projection=proj)
ax.set_extent(i_area, latlon_proj)
#
##
# ハッチ preTTd hPa面 T - Td                                                                        
cnf_ttd = ax.contourf(dsp['lon'], dsp['lat'], dsp['ttd'], levels_h_ttd, colors=levels_h_ttd_col,
                      alpha=0.2, extend='both', transform=latlon_proj )
cn_ttd = ax.contour(dsp['lon'], dsp['lat'], dsp['ttd'],
                    colors='gray', linewidths=1.0,
                    levels=levels_ttd, transform=latlon_proj )
# 等値線 preTTd hPa面 T - Td  
# colorbarの位置と大きさ指定
#  add_axes([左端の距離, 下端からの距離, 横幅, 縦幅])                                      
ax_ttd = fig.add_axes([0.1, 0.1, 0.8, 0.02])
cb_ttd = fig.colorbar(cnf_ttd, orientation='horizontal', shrink=0.74,
                      aspect=40, pad=0.01, cax=ax_ttd)
##
# preT hPa面 等温度線
dstp['temperature'] = (dstp['temperature']).metpy.convert_units(units.degC)  # Kelvin => Celsius
cn_tmp = ax.contour(dstp['lon'], dstp['lat'],dstp['temperature'],
                    colors='blue', linewidths=1.5,
                    levels=levels_tmp, transform=latlon_proj )
ax.clabel(cn_tmp, cn_tmp.levels, fontsize=12,
          inline=True, inline_spacing=5, colors='blue',
          fmt='%i', rightside_up=True)
cn_tmp1 = ax.contour(dstp['lon'], dstp['lat'],dstp['temperature'],
                     colors='blue', linewidths=2.5, levels=levels_tmp1,
                     transform=latlon_proj )
ax.clabel(cn_tmp1, cn_tmp1.levels, fontsize=12,
          inline=True, inline_spacing=5,
          fmt='%i', rightside_up=True, colors='blue')
# -30度は紫の実線とする
cn_m30 = ax.contour(dstp['lon'], dstp['lat'], dstp['temperature'],
                    colors='purple', linewidths=2.0,
                    levels=[-30], transform=latlon_proj )
#
## W スタンプ
maxid = detect_peaks(dstp['temperature'].values, filter_size=12, dist_cut=2.0)
for i in range(len(maxid[0])):
  wlon = dstp['lon'][maxid[1][i]]
  wlat = dstp['lat'][maxid[0][i]]
  # 図の範囲内に座標があるか確認                                                                                                                        
  fig_z, _, _ = transform_lonlat_to_figure((wlon,wlat),ax,proj)
  if ( fig_z[0] > 0.05 and fig_z[0] < 0.95  and fig_z[1] > 0.05 and fig_z[1] < 0.95):
    ax.text(wlon, wlat, 'W', size=16, color="red",
            ha='center', va='center', transform=latlon_proj)
# 
## C スタンプ
minid = detect_peaks(dstp['temperature'].values, filter_size=12, dist_cut=2.0, flag=1)
for i in range(len(minid[0])):
  wlon = dstp['lon'][minid[1][i]]
  wlat = dstp['lat'][minid[0][i]]
  # 図の範囲内に座標があるか確認                                                                                                                        
  fig_z, _, _ = transform_lonlat_to_figure((wlon,wlat),ax,proj)
  if ( fig_z[0] > 0.05 and fig_z[0] < 0.95  and fig_z[1] > 0.05 and fig_z[1] < 0.95):
    ax.text(wlon, wlat, 'C', size=16, color="purple",
            ha='center', va='center', transform=latlon_proj)
# 
## 海岸線など
ax.coastlines(resolution='50m', linewidth=1.6) # 海岸線の解像度を上げる  
if (flag_border):
    ax.add_feature(states_provinces, edgecolor='black', linewidth=0.5)
    ax.add_feature(country_borders, edgecolor='black', linewidth=0.5)
## グリッド線を引く                                                               
xticks=np.arange(0,360.1,dlon)
yticks=np.arange(-90,90.1,dlat)
gl = ax.gridlines(crs=ccrs.PlateCarree()
         , draw_labels=False
         , linewidth=1, alpha=0.8)
gl.xlocator = mticker.FixedLocator(xticks)
gl.ylocator = mticker.FixedLocator(yticks)
#
## Title                                                                        
fig.text(0.5,0.01,
         "ECM FT{0:d} IT:".format(ft_hours)+ dt_str+ " {0}hPa Tmp, {1}hPa T-Td".format(int(tagTmp),int(tagTTd)),
         ha='center',va='bottom', size=18)
#
# ファイル出力
output_fig_nm="ecm_{0}UTC_FT{1:03d}_fax57{2}.png".format(dt_str2,i_ft,str_area)
plt.savefig(output_fig_nm)
print("output:{}".format(output_fig_nm))
#
plt.show()


# In[ ]:




