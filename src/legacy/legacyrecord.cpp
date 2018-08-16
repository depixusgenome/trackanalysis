#include "legacy/legacyrecord.h"
#ifdef _MSC_VER
# pragma warning( disable : 4996 4244 4267 4305 4800 4477 4003 4267)
# include <Windows.h>
# define fseeko64 _fseeki64
# define ftello64 _ftelli64
# undef max
# undef min
#endif

#include <regex>
#include <fstream>
#include <cstdlib>
#include <cstdio>
#include <cmath>
#include <limits>
#include <assert.h>

// structures : record.h ...
namespace legacy
{
    namespace
    {
        typedef struct _micro_param {
            char* config_microscope_time;
            char* microscope_user_name;         /* the name of the microscope */
            char* microscope_manufacturer_name; /* the name of the microscope */
            int microscope_type;                /* COMMERCIAL or HOME_MADE      */
            char* PicoTwist_model;
            float zoom_factor;
            float zoom_min, zoom_max;
            float field_factor;
            float microscope_factor;
            float imaging_lens_focal_distance_in_mm;
            int LED_wavelength;
            // time_t config_microscope_time_t;
            // float max_LED_current;
            // float LED_current;
            // char *junk;
        } Micro_param;

        typedef struct _camera_param {
            char* config_camera_time;
            char* camera_manufacturer;
            char* camera_model;
            float camera_frequency_in_Hz;
            float pixel_clock;
            char* camera_config_file;
            char* camera_software_program;
            float x_pixel_2_microns;
            float y_pixel_2_microns;
            float pixel_h_in_microns;
            float pixel_w_in_microns;
            // time_t config_camera_time_t;
            int nb_pxl_x;
            int nb_pxl_y;
            int nb_bits;
            int interlace;
            float time_opening_factor;
            float shutter_time_us;
        } Camera_param;

        typedef struct _obj_param {
            char* config_objective_time;
            char* objective_manufacturer;
            float objective_magnification;
            int immersion_type;
            float objective_numerical_aperture;
            float immersion_index;
            float buffer_index;
            // time_t config_obj_time_t;
        } Obj_param;

        typedef struct _focus_param {
            char* config_focus_time;
            int Focus_is_piezzo;
            float Focus_max_expansion;
            char* Focus_driver;
            int Focus_direction;
            char* Focus_model;
            //  char *plugin_name;
            // int nb_bits;
            // float slew_rate;
            // float rising_time;
        } Focus_param;

        typedef struct _rotation_motor_param {
            char* config_rotation_motor_time;
            char* rotation_motor_manufacturer;
            char* rotation_motor_model;
            char* rotation_motor_controller;
            float rotation_motor_position;
            float P_rotation_motor;
            float I_rotation_motor;
            float D_rotation_motor;
            float rotation_max_velocity;
            float rotation_velocity;
            float gear_ratio;
            int nb_pulses_per_turn;
            // int direction;

        } Rotation_Motor_param;

        typedef struct _translation_motor_param {
            char* config_translation_motor_time;

            char* translation_motor_manufacturer;
            char* translation_motor_model;
            char* translation_motor_controller;
            float translation_motor_position;
            float P_translation_motor;
            float I_translation_motor;
            float D_translation_motor;
            float translation_max_velocity;
            float translation_velocity;
            float translation_max_pos;
            int translation_motor_inverted;
            float Inductive_sensor_servo_voltage;
            float zmag_ref_for_inductive_test;
            float Vcap_at_zmag_ref_test;
            float Zmag_vs_Vcap_poly_a0;
            float Zmag_vs_Vcap_poly_a1;
            float Zmag_vs_Vcap_poly_a2;
            int nb_pulses_per_mm;
            float zmag_offset;
            float motor_range;
            float motor_backslash;
            int motor_serial_nb;
            int ref_limit_switch;
            // int direction;

        } Translation_Motor_param;

        typedef struct _serial_param {
            char* config_serial_time;
            char* serial_port_str;
            int serial_port;
            int serial_BaudRate;
            int serial_ByteSize;
            int serial_StopBits;
            int serial_Parity;
            int serial_fDtrControl;
            int serial_fRtsControl;
            char* firmware_version;
            int rs232_started_fine;
        } Serial_param;

        typedef struct _experiment_parameter {
            char* project;
            char* user_firstname;
            char* user_lastname;
            char* experiment_set;
            char* experiment_name;
            char* experiment_filename;
            char* experiment_type; // Ramp, testing, opening assey, closing assay, opening+closing, rotation
                                   // assey
            int reagents_name_size;
            char** reagents_name;
            float* reagents_concentration;
            char* buffer_name;
            char* molecule_name; // hairpin name, mix name, molecule name
            char* linker_name;
            char* config_expt_time;
            //    char *protein_in_use;
            float bead_size;
            float molecule_extension;
            char *name_template;
            int scan_number;
            int bead_number;
        } Expt_param;

        // the force is expected to be F = fo exp -(a1 * zmag + a2 * zmag * zmag + ...+ ai * zmag ^ i)
        // the development holds for i < nd
        // the six indexes are for different beads
        // 0 -> MyOne
        // 1 -> M280
        // 2 -> M450

        typedef struct _Magnet_param {
            char* config_magnet_time;
            char* magnet_name;
            char* manufacturer;
            int series_nb;
            float gap;
            float zmag_contact_sample;
            int nb; // number of beads type with known parameters
            int nd[6];
            float f0[6];
            float a1[6];
            float a2[6];
            float a3[6];
            float a4[6];
        } Magnet_param;

        typedef struct _Bead_param {
            char* config_bead_time;
            char* bead_name;
            char* manufacturer;
            float radius;
            float low_field_suceptibility;
            float saturating_magnetization;
            float saturating_field;
        } Bead_param;

        typedef struct _DNA_molecule {
            char* config_molecule_time;
            char* molecule_name;
            float ssDNA_molecule_extension;
            float dsDNA_molecule_extension;
            float dsxi;
            float nick_proba;
        } DNA_molecule;

        typedef struct _pico_parameter {
            Micro_param micro_param;
            Camera_param camera_param;
            Obj_param obj_param;
            Focus_param focus_param;
            Translation_Motor_param translation_motor_param;
            Rotation_Motor_param rotation_motor_param;
            Serial_param serial_param;
            Expt_param expt_param;
            Magnet_param magnet_param;
            DNA_molecule dna_molecule;
            Bead_param bead_param;
        } Pico_parameter;

        struct _event_seg
        {
            int i_ev;
            int i_seg;
            int n_bead;
            int fixed_bead;
            int seg_start;              // the starting point index of segment
            int seg_end;                // the ending point index of segment
            int type;                   // specify if it is a Noise, Rising, Falling ... segment
            int n_badxy;                // numbers of bad tracking point in xy
            int n_badz;                 // numbers of bad tracking point in z
            int par_chg;                // indicates if zmag or rot or zobj has changed during segment
            int ispare;
            float zstart_vertex;        // Z start value of the segment assuming continuity with the previous segment
            float zend_vertex;          // Z end value of the segment assuming continuity with the next segment
            float xavg;                 // X aveage over the segment
            float xavg_er;              // error in X aveage over the segment
            float yavg;                 // Y aveage over the segment
            float yavg_er;              // error in Y aveage over the segment
            float zavg;                 // Z aveage over the segment
            float zavg_er;              // error in Z aveage over the segment
            float zstart;               // Z start value of the segment obtained by fit
            float zstart_er;            // error in Z start value of the segment
            float zend;                 // Z end value of the segment obtained by fit
            float zend_er;              // error in Z end value of the segment
            float sig_z;                // quadratic error in z on fit
            float z_ref;                // the base signal level
            float sig_z_ref;            // the quadratic error base signal level
            float zmag;
            float rot;
            float force;
            float zobj;
            float fspare;
            float dt;                   // the segment time duration
            float taux;                 // the characteristic time of fluctuation in x
            float tauy;                 // the characteristic time of fluctuation in y
            float tauz;                 // the characteristic time of fluctuation in z
        };

        struct _analyzed_event
        {
            int i_ev;
            int ev_start;               // the starting point index of the event
            int ev_end;                 // the ending point index of the event
            int type;
            char stype[64];
            int n_badxy;                // numbers of bad tracking point in xy
            int n_badz;                 // numbers of bad tracking point in z
            float zmag;
            float rot;
            float force;
            float zobj;
            int n_seg;                  // the number of segments
            int i_seg;
            _event_seg *e_s;     // the segment array
        };

        struct _stiffness_resu
        {
            int nxeff;
            float mxm;                        // mean value of x coordinate
            float dmxm;                       // error in mean value of x coordinate
            float sx2;                       // mean variance of x coordinate
            float sx4;                       // mean variance of x coordinate
            float sx2_16;                    // mean variance of x coordinate with average on 16 points
            float sx2_m2;                    // mean variance of x coordinate with bin = 2
            float sx2_m4;                    // mean variance of x coordinate with bin = 4
            float sx2_m8;                    // mean variance of x coordinate with bin = 8
            float fcx;                       // cutoff frequency in x
            float dfcx;                      // error in cutoff frequency in x
            float kx;
            float ax;                        // integral of fluctuation in x
            float dax;                       // error in integral of fluctuation in x
            float chisqx;                    // chi square in x
            float etarx;
            float etar2x;
            float detar2x;
            int x_cardinal_er;
            int nyeff;
            float mym;                        // mean value of y coordinate
            float dmym;                       // error in mean value of y coordinate
            float sy2;                       // mean variance of y coordinate
            float sy4;                       // mean variance of y coordinate
            float sy2_16;                    // mean variance of y coordinate with average on 16 points
            float sy2_m2;                    // mean variance of y coordinate with bin = 2
            float sy2_m4;                    // mean variance of y coordinate with bin = 4
            float sy2_m8;                    // mean variance of y coordinate with bin = 8
            float fcy;                       // cutoff frequency in y
            float dfcy;                      // error in cutoff frequency in y
            float ky;
            float ay;                        // integral of fluctuation in y
            float day;                       // error in integral of fluctuation in y
            float chisqy;                    // chi square in y
            float etary;
            float etar2y;
            float detar2y;
            int y_cardinal_er;
            int nzeff;
            float mzm;                        // mean value of z coordinate
            float dmzm;                       // error in mean value of z coordinate
            float sz2;                       // mean variance of z coordinate
            float sz4;                       // mean variance of z coordinate
            float sz2_16;                    // mean variance of z coordinate with average on 16 points
            float sz2_m2;                    // mean variance of z coordinate with bin = 2
            float sz2_m4;                    // mean variance of z coordinate with bin = 4
            float sz2_m8;                    // mean variance of Z coordinate with bin = 8
            float fcz;                       // cutoff frequency in z
            float dfcz;                      // error in cutoff frequency in z
            float kz;
            float az;                        // integral of fluctuation in z
            float daz;                       // error in integral of fluctuation in z
            float chisqz;                    // chi square in z
            float etarz;
            float etar2z;
            float detar2z;
            int z_cardinal_er;
            float zmag;
            float rot;
            int exp;
            float gain;
            float led;
            float zavg;                      // mean of Z avg disgarding points with bad profiles
            char* error_message;
            int i_zmag;
            int i_exp;
            int n_exp;
            float wong_x2;
            float wong_taux;
            float wong_chi2x;
            float wong_y2;
            float wong_tauy;
            float wong_chi2y;
            float wong_z2;
            float wong_tauz;
            float wong_chi2z;
            int n_lost;
        };

        struct bead_record
        {
            // all the following elements are written only in the tracking thread !
            // the other thread can only read these values
            int n_page, m_page, c_page;      // the page idexes
            int abs_pos;                     // the absolute position
            int in_page_index;               // the position of the last record in the current page
            int iparam[64];                  // an array to save int parameters
            float fparam[64];                  // an array to save float parameters
            int page_size;                   // the page size (typically 4096)
            int profile_radius;              // the profile size (in fact just the radius size)
            float **x, **y, **z;             // bead position organized in pages x[page][im_in_page]
            //  float **xt, **yt, **zt;          // bead true position
            char **n_l;                      // not lost idicator
            char **n_l2;                     // not lost post idicator
            int **profile_index;             // indicate the nearest profile in calibration image
            float *rad_prof_ref;             // reference radial profile
            int rad_prof_ref_size;           // reference radial profile size
            float ***rad_prof;               // radial profile  rad_prof[page][im_in_page][radius}
            float ***orthorad_prof;          // orthoradial profile  orthorad_prof[page][im_in_page][angle}
            int ortho_prof_size;             // the number of angular points
            float **theta;                   // bead angular position organized in pages theta[page][im_in_page]
            int kx_angle;                    // if 0 no theta register, != 0 the mode use to find angle
            int ***x_bead_prof;              // bead profile in x  x_bead_prof[page][im_in_page][radius}
            int ***x_bead_prof_diff;         // bead profile in x differential  x_bead_prof_diff[page][im_in_page][radius}
            int ***y_bead_prof;              // bead profile in y  y_bead_prof[page][im_in_page][radius}
            int ***y_bead_prof_diff;         // bead profile in y differential  y_bead_prof_diff[page][im_in_page][radius}
            int xy_tracking_type;            // type of tracking differential or normal
            float **x_er, **y_er, **z_er;    // bead position error organized in pages x_er[page][im_in_page]
            struct bead_tracking *b_t;       // the bead tracking stucture associate
            int cal_im_start;                // the position in byte in the track file of calibration image
            int cal_im_data;                 // the position in byte in the track file of calibration im data
            int cl;                          // the cross size
            int cw;                          // the cross width
            int nx_prof;                     // the profile size
            int forget_circle;
            int bp_filter;
            int bp_width;
            int movie_w;                     // width of a movie recorded centered on the bead
            int movie_h;                     // height of a movie recorded centered on the bead
            int movie_track;                 // if 1 indicates that the center of the movie image track the bead position
            int movie_xc;                    // x center of a movie recorded if movie_track == 0
            int movie_yc;                    // y center of a movie recorded if movie_track == 0
            _stiffness_resu *s_r;
            int n_s_r, m_s_r, c_s_r;         // the number of result allocated and current
            //O_i *calib_im;		   // calibration image (on reading only)
            //O_i *calib_im_fil;	           // filtered calibration image
            float minz_bead;                 // the minimum position in the calibration image
            float maxz_bead;                 // the maximum position in the calibration image
            int **event_nb;                  // data analyzing
            int **event_index;               // data analyzing
            int completely_losted;           // if set means that no valid data was recorded
            int xc_1, yc_1;                  // Bead position of previous frame
            _analyzed_event *a_e;
            int na_e, ma_e, ia_e;
        };

        struct ghost_bead_record
        {
            int bead_id; // bead number
            _analyzed_event *a_e;
            int na_e, ma_e, ia_e;
        };
    }

    /*    Structure used to record tracking data in a streaming mode.
     *    the data are memorized using pages of small size which are allocated quickly
     *    For instance the image number is store in imi[c_page][in_page_index]
     *    one page is typically 4096 records
     */
    struct gen_record
    {
        // all the following elements are written only in the tracking thread !
        // the other thread can only read these values
        int n_page, m_page, c_page;      // the page idexes
        int in_page_index;               // the position of the last record in the current page
        int page_size;                   // the page size
        int abs_pos;                     // the absolute position of valid data
        int iparam[64];                  // an array to save int parameters
        float fparam[64];                  // an array to save float parameters
        int n_bead, m_bead, c_bead;        // the bead idexes
        void * g_t;          // the pointer to the general tracking data
        bead_record **b_r;          // the bead pointer
        ghost_bead_record **b_rg;   // the ghost bead pointer to keep events of beads not loaded

        int start_bead, in_bead;           // b_r has n_bead elements b_rg has in_bead is elements = the total number of beads in trk
        int starting_fr_from_trk;          // for partial track loading
        int nb_fr_from_trk;                // for partial track loading
        int **imi;                         // the image nb
        int **imit;                        // the image nb by timer
        long long **imt;                   // the image absolute time
        unsigned int **imdt;              // the time spent in the previous function call // was long
        float **zmag;                      // the magnet position
        float **rot_mag;                   // the magnet rotation position
        float **obj_pos;                   // the objective position measured
        int **status_flag;
        float **zmag_cmd;                  // the magnet command asked
        float **rot_mag_cmd;               // the magnet rotation command asked
        float **obj_pos_cmd;               // the objective position command asked
        // all the following elements are written only in the allegro thread (in idle actions) !
        // the other thread can only read these values
        int **action_status;               // contains information like data acquisition type or point nb
        char **message;                    // runing message use to save temperature, buffer changes etc
        int last_starting_pos;              // the first position in general tracking of next recording phase
        int starting_in_page_index;        // the position of the last record in the current page
        int starting_page;                 // the absolute position
        int n_record;                      // the number of recors in this stucture
        int last_saved_pos;                // the first position of last recording phase
        int last_saved_in_page_index;      // the position of the last record in the current page
        int last_saved_page;               // the absolute position
        float ax, dx;                      // the x affine transform to microns
        float ay, dy;                      // the y affine transform to microns
        float z_cor;                       // the immersion correction 0.878
        int (*record_action)(int im, int c_i, int aci);      // the routine changing magnets or objectif
        char filename[512];
        char path[512];
        char *fullname;                    // the complete filename
        char name[512];
        int n_rec;
        int data_type;
        unsigned int time;			     // date of creation   // was time_t
        double record_duration;         // duration of data acquisition in micro seconds
        long long record_start;         // start of duration of data
        long long record_end;         // end of duration of data
        int header_state;                //
        int header_size;                // the offset to skip before real data
        int file_error;                  // report if error during saving occured
        int one_im_data_size;            // number of bytes written ay each image
        int real_time_saving;            // flag on when saving is active
        int config_file_position;
        Pico_parameter Pico_param_record;
        long long pc_ulclocks_per_sec;
        int n_events;                   // the number of events, if = n, event n was recorded
        int imi_start;                  // the image nb of the first image in trk
        int timing_mode;                // define the way to display time
        int evanescent_mode;            // are we using evanescent z measure
        float eva_decay;
        float eva_offset;
        int im_data_type;               // the type of video image
        int im_nx;                      // the x size of video image
        int im_ny;                      // the y size of video image
        int SDI_mode;
    };
}

// code : record.cc ...
namespace legacy
{
    namespace
    {
        constexpr static int const PAGE_BUFFER_SIZE              = 4096;
        constexpr static int const F_EVA_DECAY                   = 62;
        constexpr static int const F_EVA_OFFSET                  = 61;
        constexpr static int const I_EVANESCENT_MODE             = 62;
        constexpr static int const I_SDI_MODE                    = 61;
        constexpr static int const XY_TRACKING_TYPE_DIFFERENTIAL = 0x01;
        constexpr static int const XY_BEAD_PROFILE_RECORDED      = 0x04;
        constexpr static int const XY_BEAD_DIFF_PROFILE_RECORDED = 0x08;
        constexpr static int const XYZ_ERROR_RECORDED            = 0x10;
        constexpr static int const RECORD_BEAD_IMAGE             = 0x20;
        constexpr static int const IS_INT_IMAGE                  = 128;
        constexpr static int const IS_CHAR_IMAGE                 = 256;
        constexpr static int const IS_FLOAT_IMAGE                = 512;
        constexpr static int const IS_COMPLEX_IMAGE              = 64;
        constexpr static int const IS_RGB_PICTURE                = 16384;   // 0x4000
        constexpr static int const IS_BW_PICTURE                 = 32768;  // 0x8000
        constexpr static int const IS_UINT_IMAGE                 = 131072;  // 0x20000
        constexpr static int const IS_LINT_IMAGE                 = 262144;  // 0x40000
        constexpr static int const IS_RGBA_PICTURE               = 524288;  // 0x80000
        constexpr static int const IS_DOUBLE_IMAGE               = 0x200000;
        constexpr static int const IS_COMPLEX_DOUBLE_IMAGE       = 0x400000;
        constexpr static int const IS_RGB16_PICTURE              = 0x800000;
        constexpr static int const IS_RGBA16_PICTURE             = 0x100000;

#   ifdef _WIN32
        long long my_ulclocks_per_sec = 0;
        long long _get_my_ulclocks_per_sec(void)
        {
            LARGE_INTEGER freq;
            QueryPerformanceFrequency(&freq);
            my_ulclocks_per_sec = (long long)(freq.QuadPart);
            return my_ulclocks_per_sec;
        }
#   else
        long long my_ulclocks_per_sec = 1e6;
        long long _get_my_ulclocks_per_sec(void)
        {
            return my_ulclocks_per_sec;
        }
#   endif

        int grab_record_temp(gen_record *g_r, int rank, float *T0,  float *T1,  float *T2)
        {
            int  i, page_n, i_page;
            int nf, i0 = -1, i1 = -1, i2 = -1;
            float  lT0 = 0, lT1 = 0, lT2 = 0;
            char l_mes[32];
            int lmi = 0, prev = -1;

            if (g_r == NULL)
                return 1;

            nf = g_r->abs_pos;

            if (nf <= 0)
            {
                return 1;
            }

            for (i = 0, prev = 0, lmi = 0; i < nf; i++)
            {
                page_n = i / g_r->page_size;
                i_page = i % g_r->page_size;

                if (g_r->message[page_n][i_page] == 0)
                {
                    if (prev != 0 && lmi > 3)
                    {
                        if (l_mes[0] == 'T')
                        {
                            if (i0 < rank && l_mes[1] == '0' && sscanf(l_mes + 3, "%f", &lT0) == 1)
                            {
                                i0++;
                            }
                            else if (i1 < rank && l_mes[1] == '1' && sscanf(l_mes + 3, "%f", &lT1) == 1)
                            {
                                i1++;
                            }
                            else if (i2 < rank && l_mes[1] == '2' && sscanf(l_mes + 3, "%f", &lT2) == 1)
                            {
                                i2++;
                            }
                        }

                        lmi = 0;

                        if (i0 >= rank && i1 >= rank && i2 >= rank)
                        {
                            i = nf;

                            if (T0)
                            {
                                *T0 = lT0;
                            }

                            if (T1)
                            {
                                *T1 = lT1;
                            }

                            if (T2)
                            {
                                *T2 = lT2;
                            }
                        }
                    }

                    prev = 0;
                }
                else
                {
                    prev = 1;

                    if (lmi < 32)
                    {
                        l_mes[lmi++] = g_r->message[page_n][i_page];
                    }
                }
            }

            return 0;
        }

        float	compute_y_microscope_scaling_new(Obj_param *obj, Micro_param *mic, Camera_param *cam)
        {
            float fy;

            fy = mic->microscope_factor * cam->pixel_h_in_microns;
            fy /= (mic->field_factor != 0) ?  mic->field_factor : 1;
            fy /= ((float)obj->objective_magnification * mic->zoom_factor);
            fy *= ((float)175)/mic->imaging_lens_focal_distance_in_mm;
            return fy;
        }

        float	compute_x_microscope_scaling_new(Obj_param *obj, Micro_param *mic, Camera_param *cam)
        {
            float fy;

            fy = mic->microscope_factor * cam->pixel_w_in_microns;
            fy /= (mic->field_factor != 0) ?  mic->field_factor : 1;
            fy /= ((float)obj->objective_magnification * mic->zoom_factor);
            fy *= ((float)175)/mic->imaging_lens_focal_distance_in_mm;
            return fy;
        }

        float camera_known_freq(char *model, int sizex, int sizey)
        {
            float f = -1;

            if (model == NULL)
            {
                return f;
            }

            if (strstr(model, "CM-140GE") != NULL)
            {
                if (sizex ==  1392 && sizey == 1040)
                {
                    f = 31.08;
                }
                else if (sizex ==  1392 && sizey == 520)
                {
                    f = 46.57;
                }
                else if (sizex ==  1392 && sizey == 260)
                {
                    f = 61.92;
                }
                else if (sizex ==  1392 && sizey == 130)
                {
                    f = 73.97;
                }
            }
            else if (strstr(model, "BM-141GE") != NULL)
            {
                if (sizex ==  1392 && sizey == 1040)
                {
                    f = 30.12;
                }
                else if (sizex ==  1392 && sizey == 694)
                {
                    f = 41.05;
                }
                else if (sizex ==  1392 && sizey == 520)
                {
                    f = 50.06;
                }
                else if (sizex ==  1392 && sizey == 260)
                {
                    f = 74.57;
                }
                else if (sizex ==  1392 && sizey == 130)
                {
                    f = 98.73;
                }
            }
            else if (strstr(model, "CV-A10GE") != NULL)
            {
                if (sizex ==  767 && sizey == 576)
                {
                    f = 60.0;
                }
                else if (sizex ==  767 && sizey == 287)
                {
                    f = 112.0;
                }
                else if (sizex ==  767 && sizey == 143)
                {
                    f = 177.0;
                }
                else if (sizex ==  767 && sizey == 71)
                {
                    f = 250.0;
                }
            }
            else if (strstr(model, "TM-6740GE") != NULL)
            {
                if (sizex ==  640 && sizey == 480)
                {
                    f = 200.0;
                }
                else if (sizex ==  640 && sizey == 160)
                {
                    f = 540.0;
                }
                else if (sizex ==  224 && sizey == 480)
                {
                    f = 500.0;
                }
                else if (sizex ==  224 && sizey == 160)
                {
                    f = 1250.0;
                }
            }
            else if (strstr(model, "CM-030GE") != NULL)
            {
                if (sizex ==  656 && sizey == 494)
                {
                    f = 90.5;
                }
                else if (sizex ==  656 && sizey == 326)
                {
                    f = 128.0;
                }
                else if (sizex ==  656 && sizey == 246)
                {
                    f = 159.0;
                }
                else if (sizex ==  656 && sizey == 122)
                {
                    f = 255.0;
                }
                else if (sizex ==  656 && sizey == 62)
                {
                    f = 361.0;
                }
            }
            else if (strstr(model, "CM-040GE") != NULL)
            {
                if (sizex ==  776 && sizey == 582)
                {
                    f = 61.15;
                }
                else if (sizex ==  776 && sizey == 390)
                {
                    f = 87.0;
                }
                else if (sizex ==  776 && sizey == 294)
                {
                    f = 110.0;
                }
                else if (sizex ==  776 && sizey == 146)
                {
                    f = 186.0;
                }
                else if (sizex ==  776 && sizey == 74)
                {
                    f = 280.0;
                }
            }
            else if (strstr(model, "CV-M40") != NULL)
            {
                if (sizex ==  659 && sizey == 494)
                {
                    f = 60.0;
                }
            }
            else if (strstr(model, "CV-M30") != NULL)
            {
                if (sizex ==  756 && sizey == 485)
                {
                    f = 60.0;
                }
                else if (sizex ==  756 && sizey == 242)
                {
                    f = 120.0;
                }
                else if (sizex ==  756 && sizey == 111)
                {
                    f = 240.0;
                }
                else if (sizex ==  756 && sizey == 67)
                {
                    f = 360.0;
                }
            }

            return f;
        }

        float camera_known_pixelw(char *model)
        {
            float f = -1;

            if (model == NULL)
            {
                return f;
            }

            if (strstr(model, "CM-140GE") != NULL)
            {
                f = 4.65;
            }
            else if (strstr(model, "CV-A10GE") != NULL)
            {
                f = 8.3;
            }
            else if (strstr(model, "BM-141GE") != NULL)
            {
                f = 6.45;
            }
            else if (strstr(model, "TM-6740GE") != NULL)
            {
                f = 7.4;
            }
            else if (strstr(model, "CM-030GE") != NULL)
            {
                f = 7.4;
            }
            else if (strstr(model, "CM-040GE") != NULL)
            {
                f = 8.3;
            }
            else if (strstr(model, "CV-M40") != NULL)
            {
                f = 9.9;
            }
            else if (strstr(model, "CV-M30") != NULL)
            {
                f = 9.8;
            }
            else if (strstr(model, "UI324xCP-M") != NULL)
            {
                f = 5.3;
            }
            else if (strstr(model, "UI337xCP-M") != NULL)
            {
                f = 5.5;
            }

            return f;
        }

        float camera_known_pixelh(char *model)
        {
            float f = -1;

            if (model == NULL)
            {
                return f;
            }

            if (strstr(model, "CM-140GE") != NULL)
            {
                f = 4.65;
            }
            else if (strstr(model, "CV-A10GE") != NULL)
            {
                f = 8.3;
            }
            else if (strstr(model, "BM-141GE") != NULL)
            {
                f = 6.45;
            }
            else if (strstr(model, "TM-6740GE") != NULL)
            {
                f = 7.4;
            }
            else if (strstr(model, "CM-030GE") != NULL)
            {
                f = 7.4;
            }
            else if (strstr(model, "CM-040GE") != NULL)
            {
                f = 8.3;
            }
            else if (strstr(model, "CV-M40") != NULL)
            {
                f = 9.9;
            }
            else if (strstr(model, "CV-M30") != NULL)
            {
                f = 8.4;
            }
            else if (strstr(model, "UI324xCP-M") != NULL)
            {
                f = 5.3;
            }
            else if (strstr(model, "UI337xCP-M") != NULL)
            {
                f = 5.5;
            }

            return f;
        }

        Obj_param *load_Obj_param_from_trk(gen_record *g_r, int cor)
        {
            int i;
            size_t cfg_size;
            Obj_param *Ob_p = NULL;
            char buf[256], *cfg = NULL, *st = NULL, *st1 = NULL;
            FILE *fp = NULL;
            long pos = 0;

            if (g_r == NULL || g_r->fullname == NULL)
            {
                return NULL;
            }
            //setlocale(LC_ALL,"C");
            if (cor == 0)
            {
                fp = fopen(g_r->fullname, "rb");
                if (fp == NULL)
                {
                    throw TrackIOException("Could not open file: check path and rights");
                    return NULL;
                }

                fseek(fp, 0, SEEK_SET);
                fseek(fp, g_r->config_file_position, SEEK_SET);

                if (g_r->header_size - g_r->config_file_position < 0)
                {
                    return NULL;
                }

                cfg_size = (size_t)g_r->header_size - g_r->config_file_position;
                cfg = (char *)calloc(cfg_size, sizeof(char));

                if (cfg == NULL)
                {
                    return NULL;
                }

                if (fread(cfg, sizeof(char), cfg_size, fp) != cfg_size)
                {
                    return NULL;
                }

                fclose(fp);
            }
            else
            {
                std::string x = g_r->fullname;
                if(x.rfind('.') != std::string::npos)
                    x.resize(x.rfind('.'));
                x += ".cor";
                fp = fopen(x.c_str(), "rb");

                if (fp != NULL)
                {
                    fseek(fp, 0, SEEK_END);      // we go to file end
                    pos = ftell(fp);
                    fseek(fp, 0, SEEK_SET);      // we go to file start

                    if (pos <= 0)
                        return NULL;

                    cfg = (char *)calloc(pos, sizeof(char));

                    if (cfg == NULL)
                        return NULL;

                    if ((i = fread(cfg, sizeof(char), pos, fp)) != pos)
                        return NULL;

                    fclose(fp);
                }
            }

            st = strstr(cfg, "[OBJECTIVE]");

            if (st == NULL)
            {
                if (cfg != NULL)
                {
                    free(cfg);
                }

                return NULL;
            }

            Ob_p = &(g_r->Pico_param_record.obj_param);
            st1 = strstr(st, "objective_magnification");

            if (st1 != NULL)
            {
                sscanf(st1, "objective_magnification = %f", &(Ob_p->objective_magnification));
            }

            st1 = strstr(st, "immersion_type");

            if (st1 != NULL)
            {
                sscanf(st1, "immersion_type = %d", &(Ob_p->immersion_type));
            }

            st1 = strstr(st, "objective_numerical_aperture");

            if (st1 != NULL)
            {
                sscanf(st1, "objective_numerical_aperture = %f", &(Ob_p->objective_numerical_aperture));
            }

            //size = 0;
            st1 = strstr(st, "config_objective_time");

            if (st1 != NULL)
            {
                for (i = 0, st1 += strlen("config_objective_time ="); i < 254 && st1[i] != '\n'; i++)
                {
                    buf[i] = st1[i];
                }

                buf[i] = 0;
                Ob_p->config_objective_time = (char *)strdup(buf);
            }

            //size = 0;
            st1 = strstr(st, "objective_manufacturer");

            if (st1 != NULL)
            {
                for (i = 0, st1 += strlen("objective_manufacturer ="); i < 254 && st1[i] != '\n'; i++)
                {
                    buf[i] = st1[i];
                }

                buf[i] = 0;
                Ob_p->objective_manufacturer = (char *)strdup(buf);
            }

            if (cfg != NULL)
            {
                free(cfg);
            }

            return Ob_p;
        }

        Camera_param *load_Camera_param_from_trk(gen_record *g_r, int cor)
        {
            int i;
            size_t cfg_size;
            Camera_param *C_p = NULL;
            char buf[256], *cfg = NULL, *st = NULL, *st1 = NULL;
            FILE *fp = NULL;
            long pos = 0;

            if (g_r == NULL || g_r->fullname == NULL)
            {
                return NULL;
            }
            //setlocale(LC_ALL,"C");
            if (cor == 0)
            {
                fp = fopen(g_r->fullname, "rb");

                if (fp == NULL)
                {
                    throw TrackIOException("Could not open file: check path and rights");
                    return NULL;
                }

                fseek(fp, 0, SEEK_SET);
                fseek(fp, g_r->config_file_position, SEEK_SET);

                if (g_r->header_size - g_r->config_file_position < 0)
                {
                    return NULL;
                }

                cfg_size = (size_t)g_r->header_size - g_r->config_file_position;
                cfg = (char *)calloc(cfg_size, sizeof(char));

                if (cfg == NULL)
                {
                    return NULL;
                }

                if (fread(cfg, sizeof(char), cfg_size, fp) != cfg_size)
                {
                    return NULL;
                }

                fclose(fp);
            }
            else
            {
                std::string x = g_r->fullname;
                if(x.rfind('.') != std::string::npos)
                    x.resize(x.rfind('.'));
                x += ".cor";
                fp = fopen(x.c_str(), "rb");

                if (fp != NULL)
                {
                    fseek(fp, 0, SEEK_END);      // we go to file end
                    pos = ftell(fp);
                    fseek(fp, 0, SEEK_SET);      // we go to file start

                    if (pos <= 0)
                        return NULL;

                    cfg = (char *)calloc(pos, sizeof(char));

                    if (cfg == NULL)
                        return NULL;

                    if ((i = fread(cfg, sizeof(char), pos, fp)) != pos)
                        return NULL;

                    fclose(fp);
                }
            }

            st = strstr(cfg, "[CAMERA]");

            if (st == NULL)
            {
                if (cfg != NULL)
                    free(cfg);
                return NULL;
            }

            C_p = &(g_r->Pico_param_record.camera_param);
            st1 = strstr(st, "camera_frequency_in_Hz");

            if (st1 != NULL)
            {
                sscanf(st1, "camera_frequency_in_Hz = %f", &(C_p->camera_frequency_in_Hz));
            }

            st1 = strstr(st, "x_pixel_2_microns");

            if (st1 != NULL)
            {
                sscanf(st1, "x_pixel_2_microns = %f", &(C_p->x_pixel_2_microns));
            }

            st1 = strstr(st, "y_pixel_2_microns");

            if (st1 != NULL)
            {
                sscanf(st1, "y_pixel_2_microns = %f", &(C_p->y_pixel_2_microns));
            }

            st1 = strstr(st, "pixel_h_in_microns");

            if (st1 != NULL)
            {
                sscanf(st1, "pixel_h_in_microns = %f", &(C_p->pixel_h_in_microns));
            }

            st1 = strstr(st, "pixel_w_in_microns");

            if (st1 != NULL)
            {
                sscanf(st1, "pixel_w_in_microns = %f", &(C_p->pixel_w_in_microns));
            }

            st1 = strstr(st, "nb_pxl_x");

            if (st1 != NULL)
            {
                sscanf(st1, "nb_pxl_x = %d", &(C_p->nb_pxl_x));
            }

            st1 = strstr(st, "nb_pxl_y");

            if (st1 != NULL)
            {
                sscanf(st1, "nb_pxl_y = %d", &(C_p->nb_pxl_y));
            }

            st1 = strstr(st, "nb_bits");

            if (st1 != NULL)
            {
                sscanf(st1, "nb_bits = %d", &(C_p->nb_bits));
            }

            st1 = strstr(st, "interlace");

            if (st1 != NULL)
            {
                sscanf(st1, "interlace = %d", &(C_p->interlace));
            }

            //  win_printf("Camera properties \n%g Hz, x -> \\mu m %g , y -> \\mu m %g\n"
            //     "w -> \\mu m %g , h -> \\mu m %g ",C_p->camera_frequency_in_Hz,C_p->x_pixel_2_microns
            //     ,C_p->y_pixel_2_microns, C_p->pixel_w_in_microns, C_p->pixel_h_in_microns);
            //size = 0;
            st1 = strstr(st, "config_camera_time");

            if (st1 != NULL)
            {
                for (i = 0, st1 += strlen("config_camera_time ="); i < 254 && st1[i] != '\n'; i++)
                {
                    buf[i] = st1[i];
                }

                buf[i] = 0;
                C_p->config_camera_time = (char *)strdup(buf);
            }

            //size = 0;
            st1 = strstr(st, "camera_manufacturer");

            if (st1 != NULL)
            {
                for (i = 0, st1 += strlen("camera_manufacturer ="); i < 254 && st1[i] != '\n'; i++)
                {
                    buf[i] = st1[i];
                }

                buf[i] = 0;
                C_p->camera_manufacturer = (char *)strdup(buf);
            }

            //size = 0;
            st1 = strstr(st, "camera_model");

            if (st1 != NULL)
            {
                for (i = 0, st1 += strlen("camera_model ="); i < 254 && st1[i] != '\n'; i++)
                {
                    buf[i] = st1[i];
                }

                buf[i] = 0;
                C_p->camera_model = (char *)strdup(buf);
            }

            //size = 0;
            st1 = strstr(st, "camera_config_file");

            if (st1 != NULL)
            {
                for (i = 0, st1 += strlen("camera_config_file ="); i < 254 && st1[i] != '\n'; i++)
                {
                    buf[i] = st1[i];
                }

                buf[i] = 0;
                C_p->camera_config_file = (char *)strdup(buf);
            }

            //size = 0;
            st1 = strstr(st, "camera_software_program");

            if (st1 != NULL)
            {
                for (i = 0, st1 += strlen("camera_software_program ="); i < 254 && st1[i] != '\n'; i++)
                {
                    buf[i] = st1[i];
                }

                buf[i] = 0;
                C_p->camera_software_program = (char *)strdup(buf);
            }

            if (cfg != NULL)
            {
                free(cfg);
            }

            return C_p;
        }

        Magnet_param *load_Magnet_param_from_trk(gen_record *g_r, int cor)
        {
            size_t cfg_size;
            int i;
            Magnet_param *M_p = NULL;
            char buf[256], *cfg = NULL, *st = NULL, *st1 = NULL;
            FILE *fp = NULL;
            long pos = 0;

            if (g_r == NULL || g_r->fullname == NULL)
            {
                return NULL;
            }
            //setlocale(LC_ALL,"C");
            if (cor == 0)
            {
                fp = fopen(g_r->fullname, "rb");

                if (fp == NULL)
                {
                    throw TrackIOException("Could not open file: check path and rights");
                    return NULL;
                }

                fseek(fp, 0, SEEK_SET);
                fseek(fp, g_r->config_file_position, SEEK_SET);

                if (g_r->header_size - g_r->config_file_position < 0)
                {
                    return NULL;
                }

                cfg_size = (size_t)(g_r->header_size - g_r->config_file_position);
                cfg = (char *)calloc(cfg_size, sizeof(char));

                if (cfg == NULL)
                {
                    return NULL;
                }

                if (fread(cfg, sizeof(char), cfg_size, fp) != cfg_size)
                {
                    return NULL;
                }

                fclose(fp);
            }
            else
            {
                std::string x = g_r->fullname;
                if(x.rfind('.') != std::string::npos)
                    x.resize(x.rfind('.'));
                x += ".cor";
                fp = fopen(x.c_str(), "rb");

                if (fp != NULL)
                {
                    fseek(fp, 0, SEEK_END);      // we go to file end
                    pos = ftell(fp);
                    fseek(fp, 0, SEEK_SET);      // we go to file start

                    if (pos <= 0)
                        return NULL;

                    cfg = (char *)calloc(pos, sizeof(char));

                    if (cfg == NULL)
                        return NULL;

                    if ((i = fread(cfg, sizeof(char), pos, fp)) != pos)
                        return NULL;

                    fclose(fp);
                }
            }

            st = strstr(cfg, "[MAGNET]");

            if (st == NULL)
            {
                if (cfg != NULL)
                {
                    free(cfg);
                }

                return NULL;
            }

            M_p = &(g_r->Pico_param_record.magnet_param);
            st1 = strstr(st, "zmag_contact_sample");

            if (st1 != NULL)
            {
                sscanf(st1, "zmag_contact_sample = %f", &(M_p->zmag_contact_sample));
            }

            st1 = strstr(st, "gap");

            if (st1 != NULL)
            {
                sscanf(st1, "gap = %f", &(M_p->gap));
            }

            st1 = strstr(st, "series_nb");

            if (st1 != NULL)
            {
                sscanf(st1, "series_nb = %d", &(M_p->series_nb));
            }

            st1 = strstr(st, "\nnb =");

            if (st1 != NULL)
            {
                sscanf(st1, "\nnb = %d", &(M_p->nb));
            }

            for (i = 0; i < M_p->nb && i < 6; i++)
            {
                snprintf(buf, 256, "nd_%d = ", i);
                st1 = strstr(st, buf);
                //snprintf(buf, 256, "nd_%d = %%d", i);

                if (st1 != NULL)
                {
                    sscanf(st1 + strlen(buf), "%d", M_p->nd + i);
                }

                snprintf(buf, 256, "f0_%d = ", i);
                st1 = strstr(st, buf);
                //snprintf(buf, 256, "f0_%d = %%f", i);

                if (st1 != NULL)
                {
                    sscanf(st1 + strlen(buf), "%f", M_p->f0 + i);
                }

                snprintf(buf, 256, "a1_%d = ", i);
                st1 = strstr(st, buf);
                //snprintf(buf, 256, "a1_%d = %%f", i);

                if (st1 != NULL)
                {
                    sscanf(st1 + strlen(buf), "%f", M_p->a1 + i);
                }

                snprintf(buf, 256, "a2_%d = ", i);
                st1 = strstr(st, buf);
                //snprintf(buf, 256, "a2_%d = %%f", i);

                if (st1 != NULL)
                {
                    sscanf(st1 + strlen(buf), "%f", M_p->a2 + i);
                }

                snprintf(buf, 256, "a3_%d = ", i);
                st1 = strstr(st, buf);
                //snprintf(buf, 256, "a3_%d = %%f", i);

                if (st1 != NULL)
                {
                    sscanf(st1 + strlen(buf), "%f", M_p->a3 + i);
                }

                snprintf(buf, 256, "a4_%d = ", i);
                st1 = strstr(st, buf);
                //snprintf(buf, 256, "a4_%d = %%f", i);

                if (st1 != NULL)
                {
                    sscanf(st1 + strlen(buf), "%f", M_p->a4 + i);
                }
            }

            //size = 0;
            st1 = strstr(st, "config_magnet_time");

            if (st1 != NULL)
            {
                for (i = 0, st1 += strlen("config_magnet_time ="); i < 254 && st1[i] != '\n'; i++)
                {
                    buf[i] = st1[i];
                }

                buf[i] = 0;
                M_p->config_magnet_time = (char *)strdup(buf);
            }

            //size = 0;
            st1 = strstr(st, "magnet_name");

            if (st1 != NULL)
            {
                for (i = 0, st1 += strlen("magnet_name ="); i < 254 && st1[i] != '\n'; i++)
                {
                    buf[i] = st1[i];
                }

                buf[i] = 0;
                M_p->magnet_name = (char *)strdup(buf);
            }

            //size = 0;
            st1 = strstr(st, "manufacturer");

            if (st1 != NULL)
            {
                for (i = 0, st1 += strlen("manufacturer ="); i < 254 && st1[i] != '\n'; i++)
                {
                    buf[i] = st1[i];
                }

                buf[i] = 0;
                M_p->manufacturer = (char *)strdup(buf);
            }

            if (cfg != NULL)
            {
                free(cfg);
            }

            return M_p;
        }

        Micro_param *load_Micro_param_from_trk(gen_record *g_r, int cor)
        {
            int i;
            size_t cfg_size;
            Micro_param *M_p = NULL;
            char buf[256], *cfg = NULL, *st = NULL, *st1 = NULL;
            long pos = 0;
            FILE *fp = NULL;
            float tmp;

            if (g_r == NULL || g_r->fullname == NULL)
            {
                return NULL;
            }
            setlocale(LC_ALL,"C");
            if (cor == 0)
            {
                fp = fopen(g_r->fullname, "rb");

                if (fp == NULL)
                {
                    throw TrackIOException("Could not open file: check path and rights");
                    return NULL;
                }

                fseek(fp, 0, SEEK_SET);
                fseek(fp, g_r->config_file_position, SEEK_SET);

                if (g_r->header_size - g_r->config_file_position < 0)
                {
                    return NULL;
                }

                cfg_size = (size_t)g_r->header_size - g_r->config_file_position;
                cfg = (char *)calloc(cfg_size, sizeof(char));

                if (cfg == NULL)
                {
                    return NULL;
                }

                if (fread(cfg, sizeof(char), cfg_size, fp) != cfg_size)
                {
                    return NULL;
                }

                fclose(fp);
            }
            else
            {
                std::string x = g_r->fullname;
                if(x.rfind('.') != std::string::npos)
                    x.resize(x.rfind('.'));
                x += ".cor";
                fp = fopen(x.c_str(), "rb");

                if (fp != NULL)
                {
                    fseek(fp, 0, SEEK_END);      // we go to file end
                    pos = ftell(fp);
                    fseek(fp, 0, SEEK_SET);      // we go to file start

                    if (pos <= 0)
                        return NULL;

                    cfg = (char *)calloc(pos, sizeof(char));

                    if (cfg == NULL)
                        return NULL;

                    if ((i = fread(cfg, sizeof(char), pos, fp)) != pos)
                        return NULL;

                    fclose(fp);
                }
            }

            st = strstr(cfg, "[MICROSCOPE]");

            if (st == NULL)
            {
                if (cfg != NULL)
                {
                    free(cfg);
                }

                return NULL;
            }

            M_p = &(g_r->Pico_param_record.micro_param);
            //size = 0;
            st1 = strstr(st, "config_microscope_time");

            if (st1 != NULL)
            {
                for (i = 0, st1 += strlen("config_microscope_time ="); i < 254 && st1[i] != '\n'; i++)
                {
                    buf[i] = st1[i];
                }

                buf[i] = 0;
                M_p->config_microscope_time = (char *)strdup(buf);
            }

            //size = 0;
            st1 = strstr(st, "microscope_user_name");

            if (st1 != NULL)
            {
                for (i = 0, st1 += strlen("microscope_user_name ="); i < 254 && st1[i] != '\n'; i++)
                {
                    buf[i] = st1[i];
                }

                buf[i] = 0;
                M_p->microscope_user_name = (char *)strdup(buf);
            }

            st1 = strstr(st, "microscope_manufacturer_name");

            if (st1 != NULL)
            {
                for (i = 0, st1 += strlen("microscope_manufacturer_name ="); i < 254 && st1[i] != '\n'; i++)
                {
                    buf[i] = st1[i];
                }

                buf[i] = 0;
                M_p->microscope_manufacturer_name = (char *)strdup(buf);
            }

            st1 = strstr(st, "PicoTwist_model");

            if (st1 != NULL)
            {
                for (i = 0, st1 += strlen("PicoTwist_model ="); i < 254 && st1[i] != '\n'; i++)
                {
                    buf[i] = st1[i];
                }

                buf[i] = 0;
                M_p->PicoTwist_model = (char *)strdup(buf);
            }

            st1 = strstr(st, "microscope_type");

            if (st1 != NULL)
            {
                sscanf(st1, "microscope_type = %d", &(M_p->microscope_type));
            }

            st1 = strstr(st, "zoom_factor");

            if (st1 != NULL)
            {
                sscanf(st1, "zoom_factor = %f", &(M_p->zoom_factor));
            }

            st1 = strstr(st, "zoom_min");

            if (st1 != NULL)
            {
                sscanf(st1, "zoom_min = %f", &(M_p->zoom_min));
            }

            st1 = strstr(st, "zoom_max");

            if (st1 != NULL)
            {
                sscanf(st1, "zoom_max = %f", &(M_p->zoom_max));
            }

            st1 = strstr(st, "field_factor");

            if (st1 != NULL)
            {
                sscanf(st1, "field_factor = %f", &(M_p->field_factor));
            }

            st1 = strstr(st, "microscope_factor");

            if (st1 != NULL)
            {
                sscanf(st1, "microscope_factor = %f", &(M_p->microscope_factor));
            }

            st1 = strstr(st, "imaging_lens_focal_distance_in_mm");

            if (st1 != NULL)
            {
                sscanf(st1, "imaging_lens_focal_distance_in_mm = %f", &(M_p->imaging_lens_focal_distance_in_mm));
            }

            st1 = strstr(st, "LED_wavelength");

            if (st1 != NULL)
            {
                sscanf(st1, "LED_wavelength = %d", &(M_p->LED_wavelength));
            }

            if (cor != 0)
            {
                st1 = strstr(st, "im_pixel_x_in_microns");

                if (st1 != NULL)
                {
                    sscanf(st1, "im_pixel_x_in_microns = %f", &tmp);
                    g_r->dx = tmp;
                }

                st1 = strstr(st, "im_pixel_y_in_microns");

                if (st1 != NULL)
                {
                    sscanf(st1, "im_pixel_y_in_microns = %f", &tmp);
                    g_r->dy = tmp;
                }
            }

            if (cfg != NULL)
            {
                free(cfg);
            }

            return M_p;
        }

        Bead_param *load_Bead_param_from_trk(gen_record *g_r, int cor)
        {
            int i;
            size_t cfg_size;
            Bead_param *B_p = NULL;
            char buf[256], *cfg = NULL, *st = NULL, *st1 = NULL;
            FILE *fp;
            long pos = 0;

            if (g_r == NULL || g_r->fullname == NULL)
            {
                return NULL;
            }
            //setlocale(LC_ALL,"C");
            if (cor == 0)
            {
                fp = fopen(g_r->fullname, "rb");

                if (fp == NULL)
                {
                    throw TrackIOException("Could not open file: check path and rights");
                    return NULL;
                }

                fseek(fp, 0, SEEK_SET);
                fseek(fp, g_r->config_file_position, SEEK_SET);

                if (g_r->header_size - g_r->config_file_position < 0)
                {
                    return NULL;
                }

                cfg_size = (size_t)g_r->header_size - g_r->config_file_position;
                cfg = (char *)calloc(cfg_size, sizeof(char));

                if (cfg == NULL)
                {
                    return NULL;
                }

                if (fread(cfg, sizeof(char), cfg_size, fp) != cfg_size)
                {
                    return NULL;
                }

                fclose(fp);
            }
            else
            {
                std::string x = g_r->fullname;
                if(x.rfind('.') != std::string::npos)
                    x.resize(x.rfind('.'));
                x += ".cor";
                fp = fopen(x.c_str(), "rb");

                if (fp != NULL)
                {
                    fseek(fp, 0, SEEK_END);      // we go to file end
                    pos = ftell(fp);
                    fseek(fp, 0, SEEK_SET);      // we go to file start

                    if (pos <= 0)
                        return NULL;

                    cfg = (char *)calloc(pos, sizeof(char));

                    if (cfg == NULL)
                        return NULL;

                    if ((i = fread(cfg, sizeof(char), pos, fp)) != pos)
                        return NULL;

                    fclose(fp);
                }
            }

            st = strstr(cfg, "[BEAD]");

            if (st == NULL)
            {
                if (cfg != NULL)
                {
                    free(cfg);
                }

                return NULL;
            }

            B_p = &(g_r->Pico_param_record.bead_param);
            //size = 0;
            st1 = strstr(st, "config_bead_time");

            if (st1 != NULL)
            {
                for (i = 0, st1 += strlen("config_bead_time ="); i < 254 && st1[i] != '\n'; i++)
                {
                    buf[i] = st1[i];
                }

                buf[i] = 0;
                B_p->config_bead_time = (char *)strdup(buf);
            }

            //size = 0;
            st1 = strstr(st, "bead_name");

            if (st1 != NULL)
            {
                for (i = 0, st1 += strlen("bead_name ="); i < 254 && st1[i] != '\n'; i++)
                {
                    buf[i] = st1[i];
                }

                buf[i] = 0;
                B_p->bead_name = (char *)strdup(buf);
            }

            st1 = strstr(st, "manufacturer");

            if (st1 != NULL)
            {
                for (i = 0, st1 += strlen("manufacturer ="); i < 254 && st1[i] != '\n'; i++)
                {
                    buf[i] = st1[i];
                }

                buf[i] = 0;
                B_p->manufacturer = (char *)strdup(buf);
            }

            st1 = strstr(st, "radius");

            if (st1 != NULL)
            {
                sscanf(st1, "radius = %f", &(B_p->radius));
            }

            st1 = strstr(st, "low_field_suceptibility");

            if (st1 != NULL)
            {
                sscanf(st1, "low_field_suceptibility = %f", &(B_p->low_field_suceptibility));
            }

            st1 = strstr(st, "saturating_magnetization");

            if (st1 != NULL)
            {
                sscanf(st1, "saturating_magnetization = %f", &(B_p->saturating_magnetization));
            }

            st1 = strstr(st, "saturating_field");

            if (st1 != NULL)
            {
                sscanf(st1, "saturating_field = %f", &(B_p->saturating_field));
            }

            if (cfg != NULL)
            {
                free(cfg);
            }

            return B_p;
        }

        DNA_molecule *load_DNA_molecule_param_from_trk(gen_record *g_r, int cor)
        {
            int i;
            size_t cfg_size;
            DNA_molecule *Dm_p = NULL;
            char buf[256], *cfg = NULL, *st, *st1;
            FILE *fp = NULL;
            long pos = 0;

            if (g_r == NULL || g_r->fullname == NULL)
            {
                return NULL;
            }
            //setlocale(LC_ALL,"C");
            if (cor == 0)
            {
                fp = fopen(g_r->fullname, "rb");

                if (fp == NULL)
                {
                    throw TrackIOException("Could not open file: check path and rights");
                    return NULL;
                }

                fseek(fp, 0, SEEK_SET);
                fseek(fp, g_r->config_file_position, SEEK_SET);

                if (g_r->header_size - g_r->config_file_position < 0)
                {
                    return NULL;
                }

                cfg_size = (size_t)g_r->header_size - g_r->config_file_position;
                cfg = (char *)calloc(cfg_size, sizeof(char));

                if (cfg == NULL)
                {
                    return NULL;
                }

                if (fread(cfg, sizeof(char), cfg_size, fp) != cfg_size)
                {
                    return NULL;
                }

                fclose(fp);
            }
            else
            {
                std::string x = g_r->fullname;
                if(x.rfind('.') != std::string::npos)
                    x.resize(x.rfind('.'));
                x += ".cor";
                fp = fopen(x.c_str(), "rb");

                if (fp != NULL)
                {
                    fseek(fp, 0, SEEK_END);      // we go to file end
                    pos = ftell(fp);
                    fseek(fp, 0, SEEK_SET);      // we go to file start

                    if (pos <= 0)
                        return NULL;

                    cfg = (char *)calloc(pos, sizeof(char));

                    if (cfg == NULL)
                        return NULL;

                    if ((i = fread(cfg, sizeof(char), pos, fp)) != pos)
                        return NULL;

                    fclose(fp);
                }
            }

            st = strstr(cfg, "[MOLECULE]");

            if (st == NULL)
            {
                if (cfg != NULL)
                {
                    free(cfg);
                }

                return NULL;
            }

            Dm_p = &(g_r->Pico_param_record.dna_molecule);
            st1 = strstr(st, "ssDNA_molecule_extension");

            if (st1 != NULL)
            {
                sscanf(st1, "ssDNA_molecule_extension = %f", &(Dm_p->ssDNA_molecule_extension));
            }

            st1 = strstr(st, "dsDNA_molecule_extension");

            if (st1 != NULL)
            {
                sscanf(st1, "dsDNA_molecule_extension = %f", &(Dm_p->dsDNA_molecule_extension));
            }

            st1 = strstr(st, "dsxi");

            if (st1 != NULL)
            {
                sscanf(st1, "dsxi = %f", &(Dm_p->dsxi));
            }

            st1 = strstr(st, "nick_proba");

            if (st1 != NULL)
            {
                sscanf(st1, "nick_proba = %f", &(Dm_p->nick_proba));
            }

            //size = 0;
            st1 = strstr(st, "config_molecule_time");

            if (st1 != NULL)
            {
                for (i = 0, st1 += strlen("config_molecule_time ="); i < 254 && st1[i] != '\n'; i++)
                {
                    buf[i] = st1[i];
                }

                buf[i] = 0;
                Dm_p->config_molecule_time = (char *)strdup(buf);
            }

            //size = 0;
            st1 = strstr(st, "molecule_name");

            if (st1 != NULL)
            {
                for (i = 0, st1 += strlen("molecule_name ="); i < 254 && st1[i] != '\n'; i++)
                {
                    buf[i] = st1[i];
                }

                buf[i] = 0;
                Dm_p->molecule_name = (char *)strdup(buf);
            }

            if (cfg != NULL)
            {
                free(cfg);
            }

            return Dm_p;
        }

        int _addpages(bead_record *b_r, int n_pages)
        {
            int i, j;

            if (b_r == NULL)
            {
                return 1;
            }

            if (b_r->n_page + n_pages >= b_r->m_page)
            {
                for (i = b_r->m_page; i < b_r->n_page + n_pages; i += 256);

                b_r->x = (float **)realloc(b_r->x, i * sizeof(float *));

                if (b_r->x == NULL)
                {
                    return 1;
                }

                b_r->y = (float **)realloc(b_r->y, i * sizeof(float *));

                if (b_r->y == NULL)
                {
                    return 1;
                }

                b_r->z = (float **)realloc(b_r->z, i * sizeof(float *));

                if (b_r->z == NULL)
                {
                    return 1;
                }

                if (b_r->x_er != NULL)
                {
                    b_r->x_er = (float **)realloc(b_r->x_er, i * sizeof(float *));

                    if (b_r->x_er == NULL)
                    {
                        return 1;
                    }
                }

                if (b_r->y_er != NULL)
                {
                    b_r->y_er = (float **)realloc(b_r->y_er, i * sizeof(float *));

                    if (b_r->y_er == NULL)
                    {
                        return 1;
                    }
                }

                if (b_r->z_er != NULL)
                {
                    b_r->z_er = (float **)realloc(b_r->z_er, i * sizeof(float *));

                    if (b_r->z_er == NULL)
                    {
                        return 1;
                    }
                }

                if (b_r->x_bead_prof != NULL)
                {
                    b_r->x_bead_prof = (int ** *)realloc(b_r->x_bead_prof, i * sizeof(int **));

                    if (b_r->x_bead_prof == NULL)
                    {
                        return 1;
                    }
                }

                if (b_r->y_bead_prof != NULL)
                {
                    b_r->y_bead_prof = (int ** *)realloc(b_r->y_bead_prof, i * sizeof(int **));

                    if (b_r->y_bead_prof == NULL)
                    {
                        return 1;
                    }
                }

                if (b_r->x_bead_prof_diff != NULL)
                {
                    b_r->x_bead_prof_diff = (int ** *)realloc(b_r->x_bead_prof_diff, i * sizeof(int **));

                    if (b_r->x_bead_prof_diff == NULL)
                    {
                        return 1;
                    }
                }

                if (b_r->y_bead_prof_diff != NULL)
                {
                    b_r->y_bead_prof_diff = (int ** *)realloc(b_r->y_bead_prof_diff, i * sizeof(int **));

                    if (b_r->y_bead_prof_diff == NULL)
                    {
                        return 1;
                    }
                }

                if (b_r->kx_angle > 0)
                {
                    b_r->theta = (float **)realloc(b_r->theta, i * sizeof(float *));

                    if (b_r->theta == NULL)
                    {
                        return 1;
                    }
                }

                b_r->profile_index = (int **)realloc(b_r->profile_index, i * sizeof(int *));

                if (b_r->profile_index == NULL)
                {
                    return 1;
                }

                b_r->n_l = (char **)realloc(b_r->n_l, i * sizeof(char *));

                if (b_r->n_l == NULL)
                {
                    return 1;
                }

                b_r->n_l2 = (char **)realloc(b_r->n_l2, i * sizeof(char *));

                if (b_r->n_l2 == NULL)
                {
                    return 1;
                }

                if (b_r->rad_prof != NULL)
                {
                    b_r->rad_prof = (float ** *)realloc(b_r->rad_prof, i * sizeof(float **));

                    if (b_r->rad_prof == NULL)
                    {
                        return 1;
                    }
                }

                if (b_r->orthorad_prof != NULL)
                {
                    b_r->orthorad_prof = (float ** *)realloc(b_r->orthorad_prof, i * sizeof(float **));

                    if (b_r->orthorad_prof == NULL)
                    {
                        return 1;
                    }
                }

                b_r->event_nb = (int **)realloc(b_r->event_nb, i * sizeof(int *));

                if (b_r->event_nb == NULL)
                {
                    return 1;
                }

                b_r->event_index = (int **)realloc(b_r->event_index, i * sizeof(int *));

                if (b_r->event_index == NULL)
                {
                    return 1;
                }

                b_r->m_page = i;
            }

            for (i = b_r->n_page; i < b_r->n_page + n_pages; i++)
            {
                b_r->x[i] = (float *)calloc(PAGE_BUFFER_SIZE, sizeof(float));

                if (b_r->x[i] == NULL)
                {
                    return 1;
                }

                b_r->y[i] = (float *)calloc(PAGE_BUFFER_SIZE, sizeof(float));

                if (b_r->y[i] == NULL)
                {
                    return 1;
                }

                b_r->z[i] = (float *)calloc(PAGE_BUFFER_SIZE, sizeof(float));

                if (b_r->z[i] == NULL)
                {
                    return 1;
                }

                if (b_r->x_er != NULL)
                {
                    b_r->x_er[i] = (float *)calloc(PAGE_BUFFER_SIZE, sizeof(float));

                    if (b_r->x_er[i] == NULL)
                    {
                        return 1;
                    }
                }

                if (b_r->y_er != NULL)
                {
                    b_r->y_er[i] = (float *)calloc(PAGE_BUFFER_SIZE, sizeof(float));

                    if (b_r->y_er[i] == NULL)
                    {
                        return 1;
                    }
                }

                if (b_r->z_er != NULL)
                {
                    b_r->z_er[i] = (float *)calloc(PAGE_BUFFER_SIZE, sizeof(float));

                    if (b_r->z_er[i] == NULL)
                    {
                        return 1;
                    }
                }

                if (b_r->kx_angle > 0)
                {
                    b_r->theta[i] = (float *)calloc(PAGE_BUFFER_SIZE, sizeof(float));

                    if (b_r->theta[i] == NULL)
                    {
                        return 1;
                    }
                }

                b_r->profile_index[i] = (int *)calloc(PAGE_BUFFER_SIZE, sizeof(int));

                if (b_r->profile_index[i] == NULL)
                {
                    return 1;
                }

                b_r->event_nb[i] = (int *)calloc(PAGE_BUFFER_SIZE, sizeof(int));

                if (b_r->event_nb[i] == NULL)
                {
                    return 1;
                }

                b_r->event_index[i] = (int *)calloc(PAGE_BUFFER_SIZE, sizeof(int));

                if (b_r->event_index[i] == NULL)
                {
                    return 1;
                }

                b_r->n_l[i] = (char *)calloc(PAGE_BUFFER_SIZE, sizeof(char));

                if (b_r->n_l[i] == NULL)
                {
                    return 1;
                }

                b_r->n_l2[i] = (char *)calloc(PAGE_BUFFER_SIZE, sizeof(char));

                if (b_r->n_l2[i] == NULL)
                {
                    return 1;
                }

                if (b_r->rad_prof != NULL && b_r->profile_radius > 0)
                {
                    b_r->rad_prof[i] = (float **)calloc(PAGE_BUFFER_SIZE, sizeof(float *));

                    if (b_r->rad_prof[i] == NULL)
                    {
                        return 1;
                    }

                    for (j = 0; j < PAGE_BUFFER_SIZE; j++)
                    {
                        b_r->rad_prof[i][j] = (float *)calloc(b_r->profile_radius, sizeof(float));

                        if (b_r->rad_prof[i][j] == NULL)
                        {
                            return 1;
                        }
                    }
                }

                if (b_r->orthorad_prof != NULL && b_r->ortho_prof_size > 0)
                {
                    b_r->orthorad_prof[i] = (float **)calloc(PAGE_BUFFER_SIZE, sizeof(float *));

                    if (b_r->orthorad_prof[i] == NULL)
                    {
                        return 1;
                    }

                    for (j = 0; j < PAGE_BUFFER_SIZE; j++)
                    {
                        b_r->orthorad_prof[i][j] = (float *)calloc(b_r->ortho_prof_size, sizeof(float));

                        if (b_r->orthorad_prof[i][j] == NULL)
                        {
                            return 1;
                        }
                    }
                }

                if (b_r->x_bead_prof != NULL && b_r->cl > 0)
                {
                    b_r->x_bead_prof[i] = (int **)calloc(PAGE_BUFFER_SIZE, sizeof(int *));

                    if (b_r->x_bead_prof[i] == NULL)
                    {
                        return 1;
                    }

                    for (j = 0; j < PAGE_BUFFER_SIZE; j++)
                    {
                        b_r->x_bead_prof[i][j] = (int *)calloc(b_r->cl, sizeof(int));

                        if (b_r->x_bead_prof[i][j] == NULL)
                        {
                            return 1;
                        }
                    }
                }

                if (b_r->y_bead_prof != NULL && b_r->cl > 0)
                {
                    b_r->y_bead_prof[i] = (int **)calloc(PAGE_BUFFER_SIZE, sizeof(int *));

                    if (b_r->y_bead_prof[i] == NULL)
                    {
                        return 1;
                    }

                    for (j = 0; j < PAGE_BUFFER_SIZE; j++)
                    {
                        b_r->y_bead_prof[i][j] = (int *)calloc(b_r->cl, sizeof(int));

                        if (b_r->y_bead_prof[i][j] == NULL)
                        {
                            return 1;
                        }
                    }
                }

                if (b_r->x_bead_prof_diff != NULL && b_r->cl > 0)
                {
                    b_r->x_bead_prof_diff[i] = (int **)calloc(PAGE_BUFFER_SIZE, sizeof(int *));

                    if (b_r->x_bead_prof_diff[i] == NULL)
                    {
                        return 1;
                    }

                    for (j = 0; j < PAGE_BUFFER_SIZE; j++)
                    {
                        b_r->x_bead_prof_diff[i][j] = (int *)calloc(b_r->cl, sizeof(int));

                        if (b_r->x_bead_prof_diff[i][j] == NULL)
                        {
                            return 1;
                        }
                    }
                }

                if (b_r->y_bead_prof_diff != NULL && b_r->cl > 0)
                {
                    b_r->y_bead_prof_diff[i] = (int **)calloc(PAGE_BUFFER_SIZE, sizeof(int *));

                    if (b_r->y_bead_prof_diff[i] == NULL)
                    {
                        return 1;
                    }

                    for (j = 0; j < PAGE_BUFFER_SIZE; j++)
                    {
                        b_r->y_bead_prof_diff[i][j] = (int *)calloc(b_r->cl, sizeof(int));

                        if (b_r->y_bead_prof_diff[i][j] == NULL)
                        {
                            return 1;
                        }
                    }
                }
            }

            // the bead images are not stored in here, they are stored in thr trk file
            b_r->n_page += n_pages;
            return 0;
        }

        int _addpages(gen_record *g_r, int n_pages)
        {
            int i;

            //char buf[512];
            if (g_r == NULL)
                return 1;

            if (g_r->n_page + n_pages >= g_r->m_page)
            {
                for (i = g_r->m_page; i < g_r->n_page + n_pages; i += 256);

                g_r->imi = (int **)realloc(g_r->imi, i * sizeof(int *));

                if (g_r->imi == NULL)
                {
                    return 1;
                }

                g_r->imit = (int **)realloc(g_r->imit, i * sizeof(int *));

                if (g_r->imit == NULL)
                {
                    return 1;
                }

                g_r->imt = (long long **)realloc(g_r->imt, i * sizeof(long long *));

                if (g_r->imt == NULL)
                {
                    return 1;
                }

                g_r->imdt = (unsigned int **)realloc(g_r->imdt, i * sizeof(unsigned int *)); // was long

                if (g_r->imdt == NULL)
                {
                    return 1;
                }

                g_r->zmag = (float **)realloc(g_r->zmag, i * sizeof(float *));

                if (g_r->zmag == NULL)
                {
                    return 1;
                }

                g_r->rot_mag = (float **)realloc(g_r->rot_mag, i * sizeof(float *));

                if (g_r->rot_mag == NULL)
                {
                    return 1;
                }

                g_r->obj_pos = (float **)realloc(g_r->obj_pos, i * sizeof(float *));

                if (g_r->obj_pos == NULL)
                {
                    return 1;
                }

                g_r->zmag_cmd = (float **)realloc(g_r->zmag_cmd, i * sizeof(float *));

                if (g_r->zmag_cmd == NULL)
                {
                    return 1;
                }

                g_r->rot_mag_cmd = (float **)realloc(g_r->rot_mag_cmd, i * sizeof(float *));

                if (g_r->rot_mag_cmd == NULL)
                {
                    return 1;
                }

                g_r->obj_pos_cmd = (float **)realloc(g_r->obj_pos_cmd, i * sizeof(float *));

                if (g_r->obj_pos_cmd == NULL)
                {
                    return 1;
                }

                g_r->status_flag = (int **)realloc(g_r->status_flag, i * sizeof(int *));

                if (g_r->status_flag == NULL)
                {
                    return 1;
                }

                g_r->action_status = (int **)realloc(g_r->action_status, i * sizeof(int *));

                if (g_r->action_status == NULL)
                {
                    return 1;
                }

                g_r->message = (char **)realloc(g_r->message, i * sizeof(char *));

                if (g_r->message == NULL)
                {
                    return 1;
                }

                g_r->m_page = i;
            }

            for (i = g_r->n_page; i < g_r->n_page + n_pages; i++)
            {
                g_r->imi[i] = (int *)calloc(g_r->page_size, sizeof(int));

                if (g_r->imi[i] == NULL)
                {
                    return 1;
                }

                g_r->imit[i] = (int *)calloc(g_r->page_size, sizeof(int));

                if (g_r->imit[i] == NULL)
                {
                    return 1;
                }

                g_r->imt[i] = (long long *)calloc(g_r->page_size, sizeof(long long));

                if (g_r->imt[i] == NULL)
                {
                    return 1;
                }

                g_r->imdt[i] = (unsigned int *)calloc(g_r->page_size, sizeof(unsigned int)); // was long

                if (g_r->imdt[i] == NULL)
                {
                    return 1;
                }

                g_r->zmag[i] = (float *)calloc(g_r->page_size, sizeof(float));

                if (g_r->zmag[i] == NULL)
                {
                    return 1;
                }

                g_r->rot_mag[i] = (float *)calloc(g_r->page_size, sizeof(float));

                if (g_r->rot_mag[i] == NULL)
                {
                    return 1;
                }

                g_r->obj_pos[i] = (float *)calloc(g_r->page_size, sizeof(float));

                if (g_r->obj_pos[i] == NULL)
                {
                    return 1;
                }

                g_r->zmag_cmd[i] = (float *)calloc(g_r->page_size, sizeof(float));

                if (g_r->zmag_cmd[i] == NULL)
                {
                    return 1;
                }

                g_r->rot_mag_cmd[i] = (float *)calloc(g_r->page_size, sizeof(float));

                if (g_r->rot_mag_cmd[i] == NULL)
                {
                    return 1;
                }

                g_r->obj_pos_cmd[i] = (float *)calloc(g_r->page_size, sizeof(float));

                if (g_r->obj_pos_cmd[i] == NULL)
                {
                    return 1;
                }

                g_r->status_flag[i] = (int *)calloc(g_r->page_size, sizeof(int));

                if (g_r->status_flag[i] == NULL)
                {
                    return 1;
                }

                g_r->action_status[i] = (int *)calloc(g_r->page_size, sizeof(int));

                if (g_r->action_status[i] == NULL)
                {
                    return 1;
                }

                g_r->message[i] = (char *)calloc(g_r->page_size, sizeof(char));

                if (g_r->message[i] == NULL)
                {
                    return 1;
                }
            }

            g_r->n_page += n_pages;
            return 0;
        }

        bead_record *_createbead(int profile_radius, int rad_prof_ref_size, int ortho_prof_size,
                                     int save_angle_kx, int xy_tracking_type, int bead_xy_prof_size)
        {
            int i;
            bead_record *b_r = (bead_record *)calloc(1, sizeof(bead_record));

            if (b_r == NULL)
            {
                return NULL;
            }

            b_r->n_page = b_r->m_page = b_r->c_page = 0;
            b_r->abs_pos = -1; // no valid point yet
            b_r->in_page_index = 0;
            b_r->m_page = 256;
            b_r->b_t = nullptr;
            b_r->rad_prof_ref_size = rad_prof_ref_size;
            b_r->x = (float **)calloc(b_r->m_page, sizeof(float *));

            if (b_r->x == NULL)
            {
                return NULL;
            }

            b_r->y = (float **)calloc(b_r->m_page, sizeof(float *));

            if (b_r->y == NULL)
            {
                return NULL;
            }

            b_r->z = (float **)calloc(b_r->m_page, sizeof(float *));

            if (b_r->z == NULL)
            {
                return NULL;
            }

            b_r->s_r = NULL; // no stiffness results by default
            b_r->n_s_r = b_r->m_s_r = b_r->c_s_r = 0;
            b_r->profile_index = (int **)calloc(b_r->m_page, sizeof(int *));

            if (b_r->profile_index == NULL)
            {
                return NULL;
            }

            b_r->event_nb = (int **)calloc(b_r->m_page, sizeof(int *));

            if (b_r->event_nb == NULL)
            {
                return NULL;
            }

            b_r->event_index = (int **)calloc(b_r->m_page, sizeof(int *));

            if (b_r->event_index == NULL)
            {
                return NULL;
            }

            b_r->n_l = (char **)calloc(b_r->m_page, sizeof(char *));

            if (b_r->n_l == NULL)
            {
                return NULL;
            }

            b_r->n_l2 = (char **)calloc(b_r->m_page, sizeof(char *));

            if (b_r->n_l2 == NULL)
            {
                return NULL;
            }

            i = profile_radius;

            if (profile_radius)
            {
                b_r->profile_radius = i;
                b_r->rad_prof = (float ** *)calloc(b_r->m_page, sizeof(float **));

                if (b_r->rad_prof == NULL)
                {
                    return NULL;
                }
            }
            else
            {
                b_r->profile_radius = 0;
                b_r->rad_prof = NULL;
            }

            if (rad_prof_ref_size > 0)
            {
                b_r->rad_prof_ref = (float *)calloc(b_r->rad_prof_ref_size, sizeof(float));

                if (b_r->rad_prof_ref == NULL)
                {
                    return NULL;
                }
            }

            i = ortho_prof_size;

            if (ortho_prof_size)
            {
                b_r->ortho_prof_size = i;
                //win_printf("created ortho %d",b_r->ortho_prof_size);
                b_r->orthorad_prof = (float ** *)calloc(b_r->m_page, sizeof(float **));

                if (b_r->orthorad_prof == NULL)
                {
                    return NULL;
                }
            }
            else
            {
                b_r->ortho_prof_size = 0;
                b_r->orthorad_prof = NULL;
            }

            //int xy_tracking_type, int bead_xy_prof_size)

            if (xy_tracking_type & XYZ_ERROR_RECORDED)
            {
                b_r->x_er = (float **)calloc(b_r->m_page, sizeof(float *));

                if (b_r->x_er == NULL)
                {
                    return NULL;
                }

                b_r->y_er = (float **)calloc(b_r->m_page, sizeof(float *));

                if (b_r->y_er == NULL)
                {
                    return NULL;
                }

                b_r->z_er = (float **)calloc(b_r->m_page, sizeof(float *));

                if (b_r->z_er == NULL)
                {
                    return NULL;
                }
            }
            else
            {
                b_r->x_er = NULL;
                b_r->y_er = NULL;
                b_r->z_er = NULL;
            }

            b_r->cl = bead_xy_prof_size;
            b_r->xy_tracking_type = xy_tracking_type;

            if ((xy_tracking_type & XY_BEAD_PROFILE_RECORDED) && (bead_xy_prof_size > 0))
            {
                b_r->x_bead_prof = (int ** *)calloc(b_r->m_page, sizeof(int **));

                if (b_r->x_bead_prof == NULL)
                {
                    return NULL;
                }

                b_r->y_bead_prof = (int ** *)calloc(b_r->m_page, sizeof(int **));

                if (b_r->y_bead_prof == NULL)
                {
                    return NULL;
                }

                if ((xy_tracking_type & XY_TRACKING_TYPE_DIFFERENTIAL) && (xy_tracking_type & XY_BEAD_DIFF_PROFILE_RECORDED))
                {
                    b_r->x_bead_prof_diff = (int ** *)calloc(b_r->m_page, sizeof(int **));

                    if (b_r->x_bead_prof_diff == NULL)
                    {
                        return NULL;
                    }

                    b_r->y_bead_prof_diff = (int ** *)calloc(b_r->m_page, sizeof(int **));

                    if (b_r->y_bead_prof_diff == NULL)
                    {
                        return NULL;
                    }
                }
                else
                {
                    b_r->x_bead_prof_diff = NULL;
                    b_r->y_bead_prof_diff = NULL;
                }
            }
            else
            {
                b_r->x_bead_prof = NULL;
                b_r->y_bead_prof = NULL;
                b_r->x_bead_prof_diff = NULL;
                b_r->y_bead_prof_diff = NULL;
            }

            b_r->movie_w = (int)(b_r->cl);
            b_r->movie_h = (int)(b_r->cl);
            b_r->movie_w = (b_r->movie_w) ? b_r->movie_w : (int)(b_r->cl);
            b_r->movie_h = (b_r->movie_h) ? b_r->movie_h : (int)(b_r->cl);
            b_r->movie_track = 1;
            i = save_angle_kx;

            if (save_angle_kx)
            {
                b_r->kx_angle = i;

                if (i > 0)
                {
                    b_r->theta = (float **)calloc(b_r->m_page, sizeof(float *));

                    if (b_r->theta == NULL)
                    {
                        return NULL;
                    }
                }
            }
            else
            {
                b_r->kx_angle = 0;
                b_r->theta = NULL;
            }

            if (_addpages(b_r, 1))
            {
                return NULL;
            }

            b_r->cal_im_start = 0;
            b_r->cal_im_data = 0;
            b_r->a_e = (_analyzed_event *)calloc(16, sizeof(_analyzed_event));

            if (b_r->a_e == NULL)
            {
                return NULL;
            }

            b_r->na_e = b_r->ia_e = 0;
            b_r->ma_e = 16;
            return b_r;
        }

        int _freebead(bead_record *b_r)
        {
            int i, j;

            if (b_r == NULL)
            {
                return 1;
            }

            for (i = 0; i < b_r->n_page; i++)
            {
                if (b_r->x[i] != NULL)
                {
                    free(b_r->x[i]);
                    b_r->x[i] = NULL;
                }

                if (b_r->y[i] != NULL)
                {
                    free(b_r->y[i]);
                    b_r->y[i] = NULL;
                }

                if (b_r->z[i] != NULL)
                {
                    free(b_r->z[i]);
                    b_r->z[i] = NULL;
                }

                if (b_r->x_er != NULL && b_r->x_er[i] != NULL)
                {
                    free(b_r->x_er[i]);
                    b_r->x_er[i] = NULL;
                }

                if (b_r->y_er != NULL && b_r->y_er[i] != NULL)
                {
                    free(b_r->y_er[i]);
                    b_r->y_er[i] = NULL;
                }

                if (b_r->z_er != NULL && b_r->z_er[i] != NULL)
                {
                    free(b_r->z_er[i]);
                    b_r->z_er[i] = NULL;
                }

                if ((b_r->kx_angle > 0) && (b_r->theta != NULL) && (b_r->theta[i] != NULL))
                {
                    free(b_r->theta[i]);
                    b_r->theta[i] = NULL;
                }

                if (b_r->profile_index[i] != NULL)
                {
                    free(b_r->profile_index[i]);
                    b_r->profile_index[i] = NULL;
                }

                if (b_r->event_nb[i] != NULL)
                {
                    free(b_r->event_nb[i]);
                    b_r->event_nb[i] = NULL;
                }

                if (b_r->event_index[i] != NULL)
                {
                    free(b_r->event_index[i]);
                    b_r->event_index[i] = NULL;
                }

                if (b_r->n_l[i] != NULL)
                {
                    free(b_r->n_l[i]);
                    b_r->n_l[i] = NULL;
                }

                if (b_r->n_l2[i] != NULL)
                {
                    free(b_r->n_l2[i]);
                    b_r->n_l2[i] = NULL;
                }

                if (b_r->profile_radius != 0 && b_r->rad_prof != NULL)
                {
                    for (j = 0; j < PAGE_BUFFER_SIZE; j++)
                    {
                        if (b_r->rad_prof[i][j] != NULL)
                        {
                            free(b_r->rad_prof[i][j]);
                            b_r->rad_prof[i][j] = NULL;
                        }
                    }

                    if (b_r->rad_prof[i] != NULL)
                    {
                        free(b_r->rad_prof[i]);
                        b_r->rad_prof[i] = NULL;
                    }
                }

                if (b_r->ortho_prof_size != 0 && b_r->orthorad_prof != NULL)
                {
                    for (j = 0; j < PAGE_BUFFER_SIZE; j++)
                    {
                        if (b_r->orthorad_prof[i][j] != NULL)
                        {
                            free(b_r->orthorad_prof[i][j]);
                            b_r->orthorad_prof[i][j] = NULL;
                        }
                    }

                    if (b_r->orthorad_prof[i] != NULL)
                    {
                        free(b_r->orthorad_prof[i]);
                        b_r->orthorad_prof[i] = NULL;
                    }
                }

                if (b_r->x_bead_prof != NULL && b_r->x_bead_prof[i] != NULL)
                {
                    for (j = 0; j < PAGE_BUFFER_SIZE; j++)
                    {
                        if (b_r->x_bead_prof[i][j] != NULL)
                        {
                            free(b_r->x_bead_prof[i][j]);
                            b_r->x_bead_prof[i][j] = NULL;
                        }
                    }

                    free(b_r->x_bead_prof[i]);
                    b_r->x_bead_prof[i] = NULL;
                }

                if (b_r->y_bead_prof != NULL && b_r->y_bead_prof[i] != NULL)
                {
                    for (j = 0; j < PAGE_BUFFER_SIZE; j++)
                    {
                        if (b_r->y_bead_prof[i][j] != NULL)
                        {
                            free(b_r->y_bead_prof[i][j]);
                            b_r->y_bead_prof[i][j] = NULL;
                        }
                    }

                    free(b_r->y_bead_prof[i]);
                    b_r->y_bead_prof[i] = NULL;
                }

                if (b_r->x_bead_prof_diff != NULL && b_r->x_bead_prof_diff[i] != NULL)
                {
                    for (j = 0; j < PAGE_BUFFER_SIZE; j++)
                    {
                        if (b_r->x_bead_prof_diff[i][j] != NULL)
                        {
                            free(b_r->x_bead_prof_diff[i][j]);
                            b_r->x_bead_prof_diff[i][j] = NULL;
                        }
                    }

                    free(b_r->x_bead_prof_diff[i]);
                    b_r->x_bead_prof_diff[i] = NULL;
                }

                if (b_r->y_bead_prof_diff != NULL && b_r->y_bead_prof_diff[i] != NULL)
                {
                    for (j = 0; j < PAGE_BUFFER_SIZE; j++)
                    {
                        if (b_r->y_bead_prof_diff[i][j] != NULL)
                        {
                            free(b_r->y_bead_prof_diff[i][j]);
                            b_r->y_bead_prof_diff[i][j] = NULL;
                        }
                    }

                    free(b_r->y_bead_prof_diff[i]);
                    b_r->y_bead_prof_diff[i] = NULL;
                }
            }

            if (b_r->x != NULL)
            {
                free(b_r->x);
                b_r->x = NULL;
            }

            if (b_r->y != NULL)
            {
                free(b_r->y);
                b_r->y = NULL;
            }

            if (b_r->z != NULL)
            {
                free(b_r->z);
                b_r->z = NULL;
            }

            if (b_r->x_er != NULL)
            {
                free(b_r->x_er);
                b_r->x_er = NULL;
            }

            if (b_r->y_er != NULL)
            {
                free(b_r->y_er);
                b_r->y_er = NULL;
            }

            if (b_r->z_er != NULL)
            {
                free(b_r->z_er);
                b_r->z_er = NULL;
            }

            if ((b_r->kx_angle > 0) && (b_r->theta != NULL))
            {
                free(b_r->theta);
                b_r->theta = NULL;
            }

            if (b_r->profile_index != NULL)
            {
                free(b_r->profile_index);
                b_r->profile_index = NULL;
            }

            if (b_r->event_nb != NULL)
            {
                free(b_r->event_nb);
                b_r->event_nb = NULL;
            }

            if (b_r->event_index != NULL)
            {
                free(b_r->event_index);
                b_r->event_index = NULL;
            }

            if (b_r->n_l != NULL)
            {
                free(b_r->n_l);
                b_r->n_l = NULL;
            }

            if (b_r->n_l2 != NULL)
            {
                free(b_r->n_l2);
                b_r->n_l2 = NULL;
            }

            if (b_r->rad_prof != NULL)
            {
                free(b_r->rad_prof);
                b_r->rad_prof = NULL;
            }

            if (b_r->rad_prof_ref != NULL)
            {
                free(b_r->rad_prof_ref);
            }

            if (b_r->orthorad_prof != NULL)
            {
                free(b_r->orthorad_prof);
                b_r->orthorad_prof = NULL;
            }

            if (b_r->x_bead_prof != NULL)
            {
                free(b_r->x_bead_prof);
                b_r->x_bead_prof = NULL;
            }

            if (b_r->y_bead_prof != NULL)
            {
                free(b_r->y_bead_prof);
                b_r->y_bead_prof = NULL;
            }

            if (b_r->x_bead_prof_diff != NULL)
            {
                free(b_r->x_bead_prof_diff);
                b_r->x_bead_prof_diff = NULL;
            }

            if (b_r->y_bead_prof_diff != NULL)
            {
                free(b_r->y_bead_prof_diff);
                b_r->y_bead_prof_diff = NULL;
            }

            if (b_r->s_r != NULL)
            {
                free(b_r->s_r);
                b_r->s_r = NULL;
                b_r->n_s_r = b_r->m_s_r = b_r->c_s_r = 0;
            }

            b_r->n_page = b_r->m_page = b_r->c_page = 0;
            b_r->abs_pos = b_r->in_page_index = 0;
# if defined(PLAYITSAM) || defined(PIAS)

            if (b_r->a_e)
            {
                for (i = 0; i < b_r->na_e; i++)
                    if (b_r->a_e[i].e_s)
                    {
                        free(b_r->a_e[i].e_s);
                    }

                free(b_r->a_e);
                b_r->a_e = NULL;
            }

            b_r->ma_e = b_r->na_e = b_r->ia_e = 0;
# endif
            free(b_r);
            return 0;
        }


        gen_record *_creategr()
        {
            int n_pages = 1;
            gen_record *g_r = NULL;
            g_r = (gen_record *)calloc(1, sizeof(struct gen_record));

            if (g_r == NULL)
                return NULL;

            g_r->g_t = nullptr;

            g_r->n_page = g_r->m_page = g_r->c_page = 0;
            g_r->abs_pos = -1;
            g_r->in_page_index = 0;
            g_r->m_page = 256;
            g_r->page_size = PAGE_BUFFER_SIZE;
            g_r->last_starting_pos = 0;
            g_r->starting_in_page_index = 0;
            g_r->starting_page = 0;
            g_r->n_record = 0;
            g_r->last_saved_pos = 0;                // the first position of last recording phase
            g_r->last_saved_in_page_index = 0;      // the position of the last record in the current page
            g_r->last_saved_page = 0;               // the absolute position
            g_r->data_type = 0;
            g_r->pc_ulclocks_per_sec = _get_my_ulclocks_per_sec();
            g_r->imi = (int **)calloc(g_r->m_page, sizeof(int *));

            if (g_r->imi == NULL)
            {
                return NULL;
            }

            g_r->imit = (int **)calloc(g_r->m_page, sizeof(int *));

            if (g_r->imit == NULL)
            {
                return NULL;
            }

            g_r->imt = (long long **)calloc(g_r->m_page, sizeof(long long *));

            if (g_r->imt == NULL)
            {
                return NULL;
            }

            g_r->imdt = (unsigned int **)calloc(g_r->m_page, sizeof(unsigned int *)); // was long

            if (g_r->imt == NULL)
            {
                return NULL;
            }

            g_r->zmag = (float **)calloc(g_r->m_page, sizeof(float *));

            if (g_r->zmag == NULL)
            {
                return NULL;
            }

            g_r->rot_mag = (float **)calloc(g_r->m_page, sizeof(float *));

            if (g_r->rot_mag == NULL)
            {
                return NULL;
            }

            g_r->obj_pos = (float **)calloc(g_r->m_page, sizeof(float *));

            if (g_r->obj_pos == NULL)
            {
                return NULL;
            }

            g_r->zmag_cmd = (float **)calloc(g_r->m_page, sizeof(float *));

            if (g_r->zmag_cmd == NULL)
            {
                return NULL;
            }

            g_r->rot_mag_cmd = (float **)calloc(g_r->m_page, sizeof(float *));

            if (g_r->rot_mag_cmd == NULL)
            {
                return NULL;
            }

            g_r->obj_pos_cmd = (float **)calloc(g_r->m_page, sizeof(float *));

            if (g_r->obj_pos_cmd == NULL)
            {
                return NULL;
            }

            g_r->status_flag = (int **)calloc(g_r->m_page, sizeof(int *));

            if (g_r->status_flag == NULL)
            {
                return NULL;
            }

            g_r->action_status = (int **)calloc(g_r->m_page, sizeof(int *));

            if (g_r->action_status == NULL)
            {
                return NULL;
            }

            g_r->message = (char **)calloc(g_r->m_page, sizeof(char *));

            if (g_r->message == NULL)
            {
                return NULL;
            }

            _addpages(g_r, n_pages);
            //set_gen_record_starting_time(g_r);
            g_r->one_im_data_size = 0;
            g_r->real_time_saving = 0;
            return g_r;
        }

        gen_record *_readheader(char *fullname)
        {
            int i;
            FILE *fp = NULL;
            int type, file_error = 0, header_size, n_bead, one_im_data_size;//, eval_one_im_data_size;
            gen_record *g_r = NULL;
            char buf[1024], *st = NULL;
            int config_file_position = 0, nx, nxb = 0, cwb = 0, xy_tracking_type = 0;
            int profile_radius = 0, cal_im_start = 0, cal_im_data = 0, iprof = 0, ortho_prof_size = 0, kx_angle = 0;
            int64_t pos64 = 0;
            float T0 = 0,  T1,  T2;
            int64_t f_size64,tmp64;
            static int n_im, st_im, bd_st, rn_bead;
# if defined(PLAYITSAM) || defined(PIAS)
            char cor_filename[512];
# endif

            if (fullname == NULL || strlen(fullname) < 2)
                return NULL;

            fp = fopen(fullname, "rb+");
            if (fp == NULL)
            {
                throw TrackIOException("Could not open file: check path and rights");
                return NULL;
            }

            if (fseeko64(fp, 0, SEEK_END) != 0)
                return NULL;

            f_size64 = ftello64(fp);
            fseeko64(fp, 0, SEEK_SET);

            if (fread(&type, sizeof(int), 1, fp) != 1)
                file_error++;

            if ((0xFFFF0000 & type) != 0x55550000) // this is a base indentifiant
                return NULL;

            if (fread(&header_size, sizeof(int), 1, fp) != 1)
                file_error++;

            if (fread(&one_im_data_size, sizeof(int), 1, fp) != 1)
                file_error++;

            if (fread(&config_file_position, sizeof(int), 1, fp) != 1)
                file_error++;

            if (fread(&n_bead, sizeof(int), 1, fp) != 1)
                file_error++;

            tmp64 = f_size64 - header_size;
            tmp64 /= one_im_data_size;
            n_im = tmp64;
            st_im = 0;
            //fclose(fp);
            rn_bead = n_bead;
            bd_st = 0;

            n_im = -1;
            g_r = _creategr();

            if (g_r == NULL)
                return NULL;

            g_r->one_im_data_size = one_im_data_size;
            g_r->header_size = header_size;
            g_r->config_file_position = config_file_position;
            g_r->n_bead = rn_bead;
            g_r->starting_fr_from_trk = st_im;
            g_r->nb_fr_from_trk = n_im;
            g_r->in_bead = n_bead;
            bd_st = (bd_st < 0) ? 0 : bd_st;
            bd_st = (bd_st < n_bead) ? bd_st : n_bead - 1;
            g_r->start_bead = bd_st;
            g_r->n_bead = (rn_bead + bd_st < n_bead) ? rn_bead : n_bead - bd_st;
            g_r->fullname = (char *)strdup(fullname);

            for(int a = strlen(fullname); a >= 0; --a)
                if(fullname[a] == '/' || fullname[a] == '\\')
                {
                    strncpy(g_r->filename, fullname+a+1, sizeof(g_r->filename));
                    strncpy(g_r->path,     fullname,     sizeof(g_r->path) < size_t(a+1) ? sizeof(g_r->path) : size_t(a+1));
                    break;
                }

            for (i = g_r->m_bead = 32; i < g_r->n_bead; i += 32);

            g_r->m_bead = i;
            g_r->c_bead = 0;
            g_r->b_r = (bead_record **)calloc(g_r->m_bead, sizeof(bead_record *));

            if (g_r->b_r == NULL)
                return NULL;

            g_r->b_rg = (ghost_bead_record **)calloc(g_r->in_bead, sizeof(ghost_bead_record *));

            if (g_r->b_rg == NULL)
                return NULL;

            for (i = 0; i < g_r->in_bead; i++)
            {
                g_r->b_rg[i] = (ghost_bead_record *)calloc(1, sizeof(ghost_bead_record));

                if (g_r->b_rg[i] == NULL)
                    return NULL;
            }

            for (i = 0, g_r->c_bead = 0; i < g_r->in_bead; i++)
            {
                if (fread(&iprof, sizeof(int), 1, fp) != 1)
                    file_error++;

                profile_radius = 0xFF & iprof;
                ortho_prof_size = (0x0000FF00 & iprof) >> 8;
                kx_angle = (0x00FF0000 & iprof) >> 16;
                xy_tracking_type = (0xFF000000 & iprof) >> 24;
                if (fread(&cal_im_start, sizeof(int), 1, fp) != 1)
                    file_error++;

                if (fread(&cal_im_data, sizeof(int), 1, fp) != 1)
                    file_error++;

                pos64 = ftell(fp);

                // we keep only the specified beads
                if (i < g_r->start_bead || i >= g_r->start_bead + g_r->n_bead)
                    continue;

                fseeko64(fp, cal_im_start, SEEK_SET);      // we go to file end
                // we read calibration image header
                nx = 0;

                if (fread(buf, sizeof(char), 1024, fp) != 1024)
                    file_error++;

                if (strstr(buf, "% image data") != buf)
                {
                    cal_im_start += 1024;  // we have an error in some tracks we need to shift by 1k
                    fseeko64(fp, cal_im_start, SEEK_SET);      // we go to file end

                    if (fread(buf, sizeof(char), 1024, fp) != 1024)
                        file_error++;
                }

                st = strstr(buf, "-nx ");

                nxb = 0;
                cwb = 0;
                st = strstr(buf, "-src \"equally spaced");

                if (st != NULL)
                    st = strstr(st, "nxb ");

                fseeko64(fp, pos64, SEEK_SET);      // we go back where we were
                g_r->b_r[g_r->c_bead] = _createbead(profile_radius, nx, ortho_prof_size, kx_angle, xy_tracking_type, nxb);
                if (g_r->b_r[g_r->c_bead] == NULL)
                    return NULL;

                g_r->b_r[g_r->c_bead]->profile_radius = profile_radius;
                g_r->b_r[g_r->c_bead]->ortho_prof_size = ortho_prof_size;
                g_r->b_r[g_r->c_bead]->cal_im_start = cal_im_start;
                g_r->b_r[g_r->c_bead]->cal_im_data = cal_im_data;
                g_r->b_r[g_r->c_bead]->cl = nxb;
                g_r->b_r[g_r->c_bead]->cw = cwb;
                g_r->c_bead++;
            }

            if (fread(&(g_r->page_size), sizeof(int), 1, fp) != 1)
                file_error++;

            if (fread(&(g_r->n_record), sizeof(int), 1, fp) != 1)
                file_error++;

            if (fread(&(g_r->data_type), sizeof(int), 1, fp) != 1)
                file_error++;

            if (fread(&(g_r->n_rec), sizeof(int), 1, fp) != 1)
                file_error++;

            if (fread(&(g_r->time), sizeof(unsigned int), 1, fp) != 1)
                file_error++;    //todo replace time_t system

            if (fread(&(g_r->record_start), sizeof(long long), 1, fp) != 1)
                file_error++;

            if (fread(g_r->name, sizeof(char), 512, fp) != 1)
                file_error++;

            if (fread(g_r->iparam, sizeof(int), 64, fp) != 1)
                file_error++;

            if (fread(g_r->fparam, sizeof(float), 64, fp) != 1)
                file_error++;

            // we save information concerning the image tracking
            if (fread(&(g_r->ax), sizeof(float), 1, fp) != 1)
                file_error++;

            if (fread(&(g_r->dx), sizeof(float), 1, fp) != 1)
                file_error++;

            if (fread(&(g_r->ay), sizeof(float), 1, fp) != 1)
                file_error++;

            if (fread(&(g_r->dy), sizeof(float), 1, fp) != 1)
                file_error++;

            if (fread(&(g_r->im_nx), sizeof(int), 1, fp) != 1)
                file_error++;

            if (fread(&(g_r->im_ny), sizeof(int), 1, fp) != 1)
                file_error++;

            if (fread(&(g_r->im_data_type), sizeof(int), 1, fp) != 1)
                file_error++;

            fclose(fp);
            g_r->eva_decay = g_r->fparam[F_EVA_DECAY];
            g_r->eva_offset = g_r->fparam[F_EVA_OFFSET];
            g_r->evanescent_mode = g_r->iparam[I_EVANESCENT_MODE];
            g_r->SDI_mode = g_r->iparam[I_SDI_MODE];
            //need_for_calib_im = (g_r->SDI_mode) ? false : true;
            load_Obj_param_from_trk(g_r, 0);

            load_Camera_param_from_trk(g_r, 0);
            load_Magnet_param_from_trk(g_r, 0);
            load_Micro_param_from_trk(g_r, 0);
            load_Bead_param_from_trk(g_r, 0);
            load_DNA_molecule_param_from_trk(g_r, 0);
            std::string x = g_r->fullname;
            if(x.rfind('.') != std::string::npos)
                x.resize(x.rfind('.'));
            x += ".cor";
            fp = fopen(x.c_str(), "rb");

            if (fp != NULL)
            {
                fclose(fp);

                load_Obj_param_from_trk(g_r, 1);
                load_Camera_param_from_trk(g_r, 1);

                load_Magnet_param_from_trk(g_r, 1);
                load_Micro_param_from_trk(g_r, 1);
                load_Bead_param_from_trk(g_r, 1);
                load_DNA_molecule_param_from_trk(g_r, 1);
            }

            g_r->z_cor = 0.878;
            if (g_r->Pico_param_record.obj_param.immersion_type == 0)
                g_r->z_cor = 1.5;
            else if (g_r->Pico_param_record.obj_param.immersion_type == 1)
                g_r->z_cor = 1;
            else if (g_r->Pico_param_record.obj_param.immersion_type == 2)
            {
                if (g_r->Pico_param_record.obj_param.immersion_index > 0 && g_r->Pico_param_record.obj_param.buffer_index > 0)
                    g_r->z_cor = g_r->Pico_param_record.obj_param.buffer_index / g_r->Pico_param_record.obj_param.immersion_index;
                else
                    g_r->z_cor = 0.878;
            }

            camera_known_pixelw(g_r->Pico_param_record.camera_param.camera_model);
            camera_known_pixelh(g_r->Pico_param_record.camera_param.camera_model);

            camera_known_freq(g_r->Pico_param_record.camera_param.camera_model,
                              g_r->Pico_param_record.camera_param.nb_pxl_x,
                              g_r->Pico_param_record.camera_param.nb_pxl_y);

            compute_y_microscope_scaling_new(&(g_r->Pico_param_record.obj_param),
                                             &(g_r->Pico_param_record.micro_param),
                                             &(g_r->Pico_param_record.camera_param));
            compute_x_microscope_scaling_new(&(g_r->Pico_param_record.obj_param),
                                             &(g_r->Pico_param_record.micro_param),
                                             &(g_r->Pico_param_record.camera_param));

            //change_Freq_string(g_r->Pico_param_record.camera_param.camera_frequency_in_Hz);
            grab_record_temp(g_r, 0, &T0,  &T1,  &T2);
            return g_r;
        }

        int _remove_trk_NAN_data(gen_record *g_r)
        {
            using std::isnan;
            using std::isinf;
            int  j, page_n, page_n1, page_n_1, i_page,  i_page1,  i_page_1, nf, er = 0;

            if (g_r == NULL)
            {
                return -1;
            }

            nf = g_r->abs_pos;

            if (nf <= 0)
            {
                return -1;
            }

            for (j = 0; j < nf; j++)
            {
                page_n = j / g_r->page_size;
                i_page = j % g_r->page_size;

                if (isnan(g_r->rot_mag[page_n][i_page]) || isinf(g_r->rot_mag[page_n][i_page]))
                {
                    er++;

                    if (j == 0 || j == nf - 1)
                    {
                        g_r->rot_mag[page_n][i_page] = 0;
                    }
                    else
                    {
                        page_n_1 = (j - 1) / g_r->page_size;
                        i_page_1 = (j - 1) % g_r->page_size;
                        page_n1 = (j + 1) / g_r->page_size;
                        i_page1 = (j + 1) % g_r->page_size;

                        if (isnan(g_r->rot_mag[page_n_1][i_page_1]) || isnan(g_r->rot_mag[page_n1][i_page1])
                                || isinf(g_r->rot_mag[page_n_1][i_page_1]) || isinf(g_r->rot_mag[page_n1][i_page1]))
                        {
                            g_r->rot_mag[page_n][i_page] = 0;
                        }
                        else
                        {
                            g_r->rot_mag[page_n][i_page] = (g_r->rot_mag[page_n_1][i_page_1] + g_r->rot_mag[page_n1][i_page1]) / 2;
                        }
                    }
                }

                if (isnan(g_r->rot_mag_cmd[page_n][i_page]) || isinf(g_r->rot_mag_cmd[page_n][i_page]))
                {
                    er++;

                    if (j == 0 || j == nf - 1)
                    {
                        g_r->rot_mag_cmd[page_n][i_page] = 0;
                    }
                    else
                    {
                        page_n_1 = (j - 1) / g_r->page_size;
                        i_page_1 = (j - 1) % g_r->page_size;
                        page_n1 = (j + 1) / g_r->page_size;
                        i_page1 = (j + 1) % g_r->page_size;

                        if (isnan(g_r->rot_mag_cmd[page_n_1][i_page_1]) || isnan(g_r->rot_mag_cmd[page_n1][i_page1])
                                || isinf(g_r->rot_mag_cmd[page_n_1][i_page_1]) || isinf(g_r->rot_mag_cmd[page_n1][i_page1]))
                        {
                            g_r->rot_mag[page_n][i_page] = 0;
                        }
                        else
                        {
                            g_r->rot_mag_cmd[page_n][i_page] = (g_r->rot_mag_cmd[page_n_1][i_page_1] + g_r->rot_mag_cmd[page_n1][i_page1]) / 2;
                        }
                    }
                }

                if (isnan(g_r->zmag[page_n][i_page]) || isinf(g_r->zmag[page_n][i_page]))
                {
                    er++;

                    if (j == 0 || j == nf - 1)
                    {
                        g_r->zmag[page_n][i_page] = 0;
                    }
                    else
                    {
                        page_n_1 = (j - 1) / g_r->page_size;
                        i_page_1 = (j - 1) % g_r->page_size;
                        page_n1 = (j + 1) / g_r->page_size;
                        i_page1 = (j + 1) % g_r->page_size;

                        if (isnan(g_r->zmag[page_n_1][i_page_1]) || isnan(g_r->zmag[page_n1][i_page1])
                                || isinf(g_r->zmag[page_n_1][i_page_1]) || isinf(g_r->zmag[page_n1][i_page1]))
                        {
                            g_r->zmag[page_n][i_page] = 0;
                        }
                        else
                        {
                            g_r->zmag[page_n][i_page] = (g_r->zmag[page_n_1][i_page_1] + g_r->zmag[page_n1][i_page1]) / 2;
                        }
                    }
                }

                if (isnan(g_r->zmag_cmd[page_n][i_page]) || isinf(g_r->zmag_cmd[page_n][i_page]))
                {
                    er++;

                    if (j == 0 || j == nf - 1)
                    {
                        g_r->zmag_cmd[page_n][i_page] = 0;
                    }
                    else
                    {
                        page_n_1 = (j - 1) / g_r->page_size;
                        i_page_1 = (j - 1) % g_r->page_size;
                        page_n1 = (j + 1) / g_r->page_size;
                        i_page1 = (j + 1) % g_r->page_size;

                        if (isnan(g_r->zmag_cmd[page_n_1][i_page_1]) || isnan(g_r->zmag_cmd[page_n1][i_page1])
                                || isinf(g_r->zmag_cmd[page_n_1][i_page_1]) || isinf(g_r->zmag_cmd[page_n1][i_page1]))
                        {
                            g_r->zmag[page_n][i_page] = 0;
                        }
                        else
                        {
                            g_r->zmag_cmd[page_n][i_page] = (g_r->zmag_cmd[page_n_1][i_page_1] + g_r->zmag_cmd[page_n1][i_page1]) / 2;
                        }
                    }
                }
            }
            return 0;
        }

        int _readdata(gen_record *g_r, int starting_im, int n_images)
        {
            int i, j;
            FILE *fp = NULL;
            int n_im, abs_pos, tmpi;//, tmpi2;
            bead_record *b_r = NULL;
            int page_n, i_page, size;
            long long filesize, tmp64, pos64 = 0;

            if (g_r == NULL || g_r->fullname == NULL)
                return -1;

            fp = fopen(g_r->fullname, "rb");
            starting_im = g_r->starting_fr_from_trk;
            n_images = g_r->nb_fr_from_trk;

            fseeko64(fp, 0, SEEK_END);
            filesize = ftello64(fp);
            rewind(fp);
            tmp64 = filesize - g_r->header_size;
            tmp64 /= g_r->one_im_data_size;
            n_im = (int)tmp64;
            fseek(fp, g_r->header_size, SEEK_SET);
            abs_pos = g_r->abs_pos;
            abs_pos += starting_im;

            if (n_images < 0)
                n_images = n_im;

            tmp64 = (abs_pos + 1);
            tmp64 *= g_r->one_im_data_size;
            tmp64 += g_r->header_size;
            fseeko64(fp, tmp64 , SEEK_SET);
            g_r->file_error = 0;
            for (j = 0;j < n_images && abs_pos < n_im && g_r->file_error == 0; j++)
            {
                tmp64 = (abs_pos + 1);
                tmp64 *= g_r->one_im_data_size;
                tmp64 += g_r->header_size;
                fseeko64(fp, tmp64 , SEEK_SET);
                abs_pos++;   // g_r->abs_pos; always pointing to a valid value, temprary variable

                if ((j + 1) >= g_r->n_page * g_r->page_size)
                {
                    if (_addpages(g_r, 1))
                    {
                        fclose(fp);
                        return 1;
                    }

                    for (i = 0; i < g_r->n_bead; i++)
                        if (_addpages(g_r->b_r[i], 1))
                        {
                            fclose(fp);
                            return 1;
                        }
                }

                if (g_r->page_size)
                {
                    page_n = j / g_r->page_size;
                    i_page = j % g_r->page_size;
                }
                else
                {
                    page_n = j / PAGE_BUFFER_SIZE;
                    i_page = j % PAGE_BUFFER_SIZE;
                }

                if (fread(g_r->imi[page_n] + i_page, sizeof(int), 1, fp) != 1)
                    g_r->file_error++;

                if (fread(g_r->imit[page_n] + i_page, sizeof(int), 1, fp) != 1)
                    g_r->file_error++;

                if (fread(g_r->imt[page_n] + i_page, sizeof(long long), 1, fp) != 1)
                    g_r->file_error++;

                if (fread(g_r->imdt[page_n] + i_page, sizeof(unsigned int), 1, fp) != 1)
                    g_r->file_error++;    // long

                if (fread(g_r->zmag[page_n] + i_page, sizeof(float), 1, fp) != 1)
                    g_r->file_error++;

                if (fread(g_r->rot_mag[page_n] + i_page, sizeof(float), 1, fp) != 1)
                    g_r->file_error++;

                if (fread(g_r->obj_pos[page_n] + i_page, sizeof(float), 1, fp) != 1)
                    g_r->file_error++;

                if (fread(g_r->status_flag[page_n] + i_page, sizeof(int), 1, fp) != 1)
                    g_r->file_error++;

                if (fread(g_r->zmag_cmd[page_n] + i_page, sizeof(float), 1, fp) != 1)
                    g_r->file_error++;

                if (fread(g_r->rot_mag_cmd[page_n] + i_page, sizeof(float), 1, fp) != 1)
                    g_r->file_error++;

                if (fread(g_r->obj_pos_cmd[page_n] + i_page, sizeof(float), 1, fp) != 1)
                    g_r->file_error++;

                if (fread(g_r->action_status[page_n] + i_page, sizeof(int), 1, fp) != 1)
                    g_r->file_error++;

                if (fread(g_r->message[page_n] + i_page, sizeof(char), 1, fp) != 1)
                    g_r->file_error++;

                for (i = 0, g_r->c_bead = 0; i < g_r->in_bead; i++)
                {
                    if (i < g_r->start_bead || i >= g_r->start_bead + g_r->n_bead)
                    {
                        b_r = g_r->b_r[0];
                        size = 3 * sizeof(float);

                        if (b_r->kx_angle)
                        {
                            size += sizeof(float);
                        }

                        size += sizeof(char);
                        size += sizeof(int);

                        if (b_r->rad_prof != NULL && b_r->profile_radius > 0)
                        {
                            size += b_r->profile_radius * sizeof(float);
                        }

                        if (b_r->orthorad_prof != NULL && b_r->ortho_prof_size > 0)
                        {
                            size += b_r->ortho_prof_size * sizeof(float);
                        }

                        if (b_r->x_er != NULL)
                        {
                            size += sizeof(float);
                        }

                        if (b_r->y_er != NULL)
                        {
                            size += sizeof(float);
                        }

                        if (b_r->z_er != NULL)
                        {
                            size += sizeof(float);
                        }

                        if (b_r->x_bead_prof != NULL && b_r->cl > 0)
                        {
                            size += b_r->cl * sizeof(int);
                        }

                        if (b_r->y_bead_prof != NULL && b_r->cl > 0)
                        {
                            size += b_r->cl * sizeof(int);
                        }

                        if (b_r->x_bead_prof_diff != NULL && b_r->cl > 0)
                        {
                            size += b_r->cl * sizeof(int);
                        }

                        if (b_r->y_bead_prof_diff != NULL && b_r->cl > 0)
                        {
                            size += b_r->cl * sizeof(int);
                        }

                        pos64 = ftello64(fp);
                        fseeko64(fp, pos64 + size , SEEK_SET);
                        continue;
                    }

                    b_r = g_r->b_r[g_r->c_bead];

                    if (fread(b_r->x[page_n] + i_page, sizeof(float), 1, fp) != 1)
                    {
                        g_r->file_error++;
                    }

                    if (fread(b_r->y[page_n] + i_page, sizeof(float), 1, fp) != 1)
                    {
                        g_r->file_error++;
                    }

                    if (fread(b_r->z[page_n] + i_page, sizeof(float), 1, fp) != 1)
                    {
                        g_r->file_error++;
                    }

                    if (b_r->kx_angle)
                    {
                      if (fread(b_r->theta[page_n] + i_page, sizeof(float), 1, fp) != 1)
                      {
                        g_r->file_error++;
                      }
                    }

                    if (fread(b_r->n_l[page_n] + i_page, sizeof(char), 1, fp) != 1)
                    {
                        g_r->file_error++;
                    }

                    if (fread(b_r->profile_index[page_n] + i_page, sizeof(int), 1, fp) != 1)
                    {
                        g_r->file_error++;
                    }

                    if (b_r->rad_prof != NULL && b_r->profile_radius > 0)
                    {
                        if (fread(b_r->rad_prof[page_n][i_page], sizeof(float),
                                  b_r->profile_radius, fp) != (size_t)b_r->profile_radius)
                        {
                            g_r->file_error++;
                        }
                    }

                    if (b_r->orthorad_prof != NULL && b_r->ortho_prof_size > 0)
                    {
                        if (fread(b_r->orthorad_prof[page_n][i_page], sizeof(float),
                                  b_r->ortho_prof_size, fp) != (size_t)b_r->ortho_prof_size)
                        {
                            g_r->file_error++;
                        }
                    }

                    if (b_r->x_er != NULL)
                        if (fread(b_r->x_er[page_n] + i_page, sizeof(float), 1, fp) != 1)
                        {
                            g_r->file_error++;
                        }

                    if (b_r->y_er != NULL)
                        if (fread(b_r->y_er[page_n] + i_page, sizeof(float), 1, fp) != 1)
                        {
                            g_r->file_error++;
                        }

                    if (b_r->z_er != NULL)
                        if (fread(b_r->z_er[page_n] + i_page, sizeof(float), 1, fp) != 1)
                        {
                            g_r->file_error++;
                        }

                    if (b_r->x_bead_prof != NULL && b_r->cl > 0)
                    {
                        if (fread(b_r->x_bead_prof[page_n][i_page], sizeof(int), b_r->cl, fp) != (size_t)b_r->cl)
                        {
                            g_r->file_error++;
                        }
                    }

                    if (b_r->y_bead_prof != NULL && b_r->cl > 0)
                    {
                        if (fread(b_r->y_bead_prof[page_n][i_page], sizeof(int), b_r->cl, fp) != (size_t)b_r->cl)
                        {
                            g_r->file_error++;
                        }
                    }

                    if (b_r->x_bead_prof_diff != NULL && b_r->cl > 0)
                    {
                        if (fread(b_r->x_bead_prof_diff[page_n][i_page], sizeof(int), b_r->cl, fp) != (size_t)b_r->cl)
                        {
                            g_r->file_error++;
                        }
                    }

                    if (b_r->y_bead_prof_diff != NULL && b_r->cl > 0)
                    {
                        if (fread(b_r->y_bead_prof_diff[page_n][i_page], sizeof(int), b_r->cl, fp) != (size_t)b_r->cl)
                        {
                            g_r->file_error++;
                        }
                    }

                    g_r->c_bead++;
                }

                for (i = 0, g_r->c_bead = 0; i < g_r->in_bead; i++)
                {
                    b_r = g_r->b_r[0];

                    if (b_r->xy_tracking_type & RECORD_BEAD_IMAGE)
                    {
                        if (fread(&tmpi, sizeof(int), 1, fp) != 1)
                        {
                            g_r->file_error++;
                        }

                        if (i >= g_r->start_bead || i < g_r->start_bead + g_r->n_bead)
                        {
                            b_r = g_r->b_r[g_r->c_bead];
                            b_r->movie_xc = tmpi & 0xFFFF;
                            b_r->movie_w = (tmpi & 0x0FFF0000) >> 16; // we limit size to 4095
                            b_r->movie_w = (b_r->movie_w) ? b_r->movie_w : b_r->cl;
                        }

                        if (fread(&tmpi, sizeof(int), 1, fp) != 1)
                        {
                            g_r->file_error++;
                        }

                        if (i >= g_r->start_bead || i < g_r->start_bead + g_r->n_bead)
                        {
                            b_r->movie_yc = tmpi & 0xFFFF;
                            //tmpi2 = tmpi;
                            b_r->movie_h = (tmpi & 0x0FFF0000) >> 16; // we limit size to 4095
                            b_r->movie_h = (b_r->movie_h) ? b_r->movie_h : b_r->cl;
                            //if (j <1) win_printf("bead %d Movie w %d h %d\n pos x %d y %d\ntmpi 0x%0x tmpi2 0x%0x"
                            //           ,i,b_r->movie_w,b_r->movie_h,tmpi&0xFFFF,tmpi2&0xFFFF,tmpi,tmpi2);
                            g_r->c_bead++;
                        }

                        pos64 = ftello64(fp);

                        if (g_r->im_data_type == IS_CHAR_IMAGE)
                        {
                            pos64 += sizeof(char) * b_r->movie_w * b_r->movie_h;
                        }
                        else if (g_r->im_data_type == IS_UINT_IMAGE)
                        {
                            pos64 += sizeof(unsigned short int) * b_r->movie_w * b_r->movie_h;
                        }

                        fseeko64(fp, pos64, SEEK_SET);
                    }
                }

                if (g_r->file_error == 0)
                {
                    g_r->abs_pos = j + 1;    //abs_pos;  // now data is valid at abs_pos
                }

                g_r->imi_start = g_r->imi[0][0];  // time origin
                g_r->timing_mode = 1;
            }

            fclose(fp);
            _remove_trk_NAN_data(g_r);
            return 0;
        }

        int _retrieve_min_max_event_and_phases(gen_record const *g_r, int *min, int *max, int *ph_max)
        {
            int  j, found = 0, page_n, i_page, point;
            int nf, first = 1, pmax, ph, lmin = std::numeric_limits<int>::max(),
                lmax = -std::numeric_limits<int>::max();

            if (g_r == NULL)
            {
                return -1;
            }

            nf = g_r->abs_pos;

            if (nf <= 0)
            {
                return -2;
            }

            for (j = 0, found = 0, pmax = 0; j < nf; j++)
            {
                page_n = j / g_r->page_size;
                i_page = j % g_r->page_size;
                point = (0xffff & (g_r->action_status[page_n][i_page] >> 8));
                ph = (0xff & (g_r->action_status[page_n][i_page]));

                if (first)
                {
                    lmin = lmax = point;
                    first = 0;
                }

                if (point < lmin)
                {
                    lmin = point;
                    found |= 1;
                }

                if (point > lmax)
                {
                    lmax = point;
                    found |= 2;
                }

                if (point > 0 && ph > pmax)
                {
                    pmax = ph;
                }
            }

            if (min)
            {
                *min = lmin;
            }

            if (max)
            {
                *max = lmax;
            }

            if (ph_max)
            {
                *ph_max = pmax;
            }

            return (found == 3) ? 0 : -3;
        }

        /*
        int _retrieve_image_index_of_next_point(gen_record const *g_r,
                                               int n_point,    // specify the point
                                               int *start_index,           // return the start index, you can specify
                                               //a possible starting point from where the
                                               //search will be initiated
                                               int *ending)
        {
            int  prev, j, found = 0, page_n, i_page, point;
            int nf, ims = 0, im0 = 0;

            if (g_r == NULL)
            {
                return -1;
            }

            nf = g_r->abs_pos;

            if (nf <= 0)
            {
                return -2;
            }

            if (*start_index >= nf)
            {
                return -3;
            }

            for (found = 0, j = *start_index, prev = 0; j < nf && found == 0; j++)
            {
                page_n = j / g_r->page_size;
                i_page = j % g_r->page_size;
                point = (0xffff & (g_r->action_status[page_n][i_page] >> 8));

                if (point == n_point)
                {
                    if (prev == 0)
                    {
                        *start_index = im0 = j;
                    }

                    ims = j;
                    prev = 1;
                }
                else if (prev == 1)
                {
                    found = 1;
                    ims = j;
                }
            }

            if (found == 0)
            {
                for (found = 0, j = 0, prev = 0; j < nf && found == 0; j++)
                {
                    page_n = j / g_r->page_size;
                    i_page = j % g_r->page_size;
                    point = (0xffff & (g_r->action_status[page_n][i_page] >> 8));

                    if (point == n_point)
                    {
                        if (prev == 0)
                        {
                            *start_index = im0 = j;
                        }

                        ims = j;
                        prev = 1;
                    }
                    else if (prev == 1)
                    {
                        found = 1;
                        ims = j;
                    }
                }
            }

            if (found == 0)
            {
                return -4;
            }

            if (ending != NULL)
            {
                *ending = ims;
            }

            return im0;
        }*/

        int _retrieve_image_index_of_next_point_phase(gen_record const *g_r,
                int n_point, int n_phase,   // specify the point and phase
                int *start_index,           // return the start index, you can specify
                //a possible starting point from where the
                //search will be initiated
                int *ending,
                int *param_cst)
        {
            int  prev, j, found = 0, page_n, i_page, point, phase;
            int nf, ims = 0, im0 = 0;

            if (g_r == NULL)
            {
                return -1;
            }

            nf = g_r->abs_pos;

            if (nf <= 0)
            {
                return -2;
            }

            *param_cst = 1;

            if (*start_index >= nf)
            {
                return -3;
            }

            if (n_phase == 0)
            {
                n_point--;    // phase 0 bug
            }

            for (found = 0, j = *start_index, prev = 0; j < nf && found == 0; j++)
            {
                page_n = j / g_r->page_size;
                i_page = j % g_r->page_size;
                point = (0xffff & (g_r->action_status[page_n][i_page] >> 8));
                phase = (0xff & (g_r->action_status[page_n][i_page]));

                if (point == n_point && phase == n_phase)
                {
                    if (prev == 0)
                    {
                        *start_index = im0 = j;
                    }

                    ims = j;

                    if (g_r->status_flag[page_n][i_page] != 0)
                    {
                        *param_cst = 0;
                    }

                    prev = 1;
                }
                else if (prev == 1)
                {
                    found = 1;
                    ims = j;
                }
            }

            if (found == 0)
            {
                for (found = 0, j = 0, prev = 0; j < nf && found == 0; j++)
                {
                    page_n = j / g_r->page_size;
                    i_page = j % g_r->page_size;
                    point = (0xffff & (g_r->action_status[page_n][i_page] >> 8));
                    phase = (0xff & (g_r->action_status[page_n][i_page]));

                    if (point == n_point && phase == n_phase)
                    {
                        if (prev == 0)
                        {
                            *start_index = im0 = j;
                        }

                        ims = j;

                        if (g_r->status_flag[page_n][i_page] != 0)
                        {
                            *param_cst = 0;
                        }

                        prev = 1;
                    }
                    else if (prev == 1)
                    {
                        found = 1;
                        ims = j;
                    }
                }
            }

            if (ending != NULL)
            {
                *ending = ims;
            }

            if (found == 0)
            {
                return -4;
            }

            return im0;
        }
    }

    int freegr(gen_record *g_r)
    {
        int i;

        if (g_r == NULL)
        {
            return 1;
        }

        for (i = 0; i < g_r->n_bead; i++)
        {
            _freebead(g_r->b_r[i]);
        }

        for (i = 0; i < g_r->n_page; i++)
        {
            if (g_r->imi[i] != NULL)
            {
                free(g_r->imi[i]);
                g_r->imi[i] = NULL;
            }

            if (g_r->imit[i] != NULL)
            {
                free(g_r->imt[i]);
                g_r->imt[i] = NULL;
            }

            if (g_r->imt[i] != NULL)
            {
                free(g_r->imdt[i]);
                g_r->imdt[i] = NULL;
            }

            if (g_r->zmag[i] != NULL)
            {
                free(g_r->zmag[i]);
                g_r->zmag[i] = NULL;
            }

            if (g_r->rot_mag[i] != NULL)
            {
                free(g_r->rot_mag[i]);
                g_r->rot_mag[i] = NULL;
            }

            if (g_r->obj_pos[i] != NULL)
            {
                free(g_r->obj_pos[i]);
                g_r->obj_pos[i] = NULL;
            }

            if (g_r->zmag_cmd[i] != NULL)
            {
                free(g_r->zmag_cmd[i]);
                g_r->zmag_cmd[i] = NULL;
            }

            if (g_r->rot_mag_cmd[i] != NULL)
            {
                free(g_r->rot_mag_cmd[i]);
                g_r->rot_mag_cmd[i] = NULL;
            }

            if (g_r->status_flag[i] != NULL)
            {
                free(g_r->status_flag[i]);
                g_r->status_flag[i] = NULL;
            }

            if (g_r->action_status[i] != NULL)
            {
                free(g_r->action_status[i]);
                g_r->action_status[i] = NULL;
            }

            if (g_r->message[i] != NULL)
            {
                free(g_r->message[i]);
                g_r->message[i] = NULL;
            }
        }

        if (g_r->imi != NULL)
        {
            free(g_r->imi);
            g_r->imi = NULL;
        }

        if (g_r->imit != NULL)
        {
            free(g_r->imt);
            g_r->imt = NULL;
        }

        if (g_r->imt != NULL)
        {
            free(g_r->imdt);
            g_r->imdt = NULL;
        }

        if (g_r->zmag != NULL)
        {
            free(g_r->zmag);
            g_r->zmag = NULL;
        }

        if (g_r->rot_mag != NULL)
        {
            free(g_r->rot_mag);
            g_r->rot_mag = NULL;
        }

        if (g_r->obj_pos != NULL)
        {
            free(g_r->obj_pos);
            g_r->obj_pos = NULL;
        }

        if (g_r->zmag_cmd != NULL)
        {
            free(g_r->zmag_cmd);
            g_r->zmag_cmd = NULL;
        }

        if (g_r->rot_mag_cmd != NULL)
        {
            free(g_r->rot_mag_cmd);
            g_r->rot_mag_cmd = NULL;
        }

        if (g_r->status_flag != NULL)
        {
            free(g_r->status_flag);
            g_r->status_flag = NULL;
        }

        if (g_r->action_status != NULL)
        {
            free(g_r->action_status);
            g_r->action_status = NULL;
        }

        if (g_r->message != NULL)
        {
            free(g_r->message);
            g_r->message = NULL;
        }

        if (g_r->fullname != NULL)
        {
            free(g_r->fullname);
        }

        g_r->fullname = NULL;
        g_r->n_page = g_r->m_page = g_r->c_page = 0;
        g_r->abs_pos = g_r->in_page_index = 0;
        g_r->page_size = 0;
        g_r->last_starting_pos = 0;
        g_r->starting_in_page_index = 0;
        g_r->starting_page = 0;
        g_r->n_record = 0;
        g_r->last_saved_pos = 0;
        g_r->last_saved_in_page_index = 0;
        g_r->last_saved_page = 0;
        g_r->m_bead = g_r->n_bead = g_r->c_bead = 0;
        free(g_r);
        return 0;
    }

    gen_record* load(char *fullfile)
    {
        gen_record *g_r = _readheader(fullfile);
        if (g_r == nullptr)
            return nullptr;

        FILE *fp = fopen(g_r->fullname, "rb");
        if (fp == NULL)
        {
            freegr(g_r);
            throw TrackIOException("could not open file");
        }

        fseeko64(fp, 0, SEEK_END);
        int64_t f_size64 = ftello64(fp);
        fseeko64(fp, g_r->header_size, SEEK_SET);
        int64_t tmp64 = f_size64 - g_r->header_size;
        tmp64 /= g_r->one_im_data_size;
        fclose(fp);

        int n_im = tmp64;
        int st_im = 0;
        if (_readdata(g_r, st_im, n_im))
        {
            freegr(g_r);
            throw TrackIOException("Problem reading track file");
        }
        return g_r;
    }

    int _get_image_stats(gen_record *g_r, int & nx, int & ny, int & data_type)
    {
        FILE *fp = NULL;
        int file_error = 0;
        long pos = 0;

        fp = fopen(g_r->fullname, "rb+");
        if (fp == NULL)
            return {};

        pos = 9 * sizeof(int) + g_r->in_bead * (3 * sizeof(int)) + sizeof(unsigned int); //todo : fix time_t system
        pos += sizeof(long long) + 512 * sizeof(char) + 64 * sizeof(int) + 64 * sizeof(float);
        pos += 4 * sizeof(float);
        fseek(fp, pos, SEEK_SET);      // we go to file end

        if (fread(&nx, sizeof(int), 1, fp) != 1)
            file_error++;

        if (fread(&ny, sizeof(int), 1, fp) != 1)
            file_error++;

        if (fread(&data_type, sizeof(int), 1, fp) != 1)
            file_error++;

        fclose(fp);
        return file_error;
    }

    template <typename T>
    void * _read(int nx, int ny, FILE * fp)
    {
        auto table = new T[nx*ny];
        auto sz = fread(table, sizeof(T), nx*ny, fp);
        sz += 1;
        return (void*) table;
    }

    int _read_mic_image(gen_record *g_r,
                        int & nx, int & ny, int & data_type, void *&ptr)
    {
        FILE *fp = NULL;
        int file_error = 0;
        long pos = 0;

        fp = fopen(g_r->fullname, "rb+");
        if (fp == NULL)
            return {};

        pos = 9 * sizeof(int) + g_r->in_bead * (3 * sizeof(int)) + sizeof(unsigned int); //todo : fix time_t system
        pos += sizeof(long long) + 512 * sizeof(char) + 64 * sizeof(int) + 64 * sizeof(float);
        pos += 4 * sizeof(float);
        fseek(fp, pos, SEEK_SET);      // we go to file end

        if (fread(&nx, sizeof(int), 1, fp) != 1)
            file_error++;

        if (fread(&ny, sizeof(int), 1, fp) != 1)
            file_error++;

        if (fread(&data_type, sizeof(int), 1, fp) != 1)
            file_error++;

        if (data_type == IS_CHAR_IMAGE)
            ptr = _read<char>(nx, ny, fp);
        else if (data_type == IS_RGB_PICTURE)
            assert(false);
        else if (data_type == IS_RGBA_PICTURE)
            assert(false);
        else if (data_type == IS_RGB16_PICTURE)
            assert(false);
        else if (data_type == IS_RGBA16_PICTURE)
            assert(false);
        else if (data_type == IS_INT_IMAGE)
            ptr = _read<short int>(nx, ny, fp);
        else if (data_type == IS_UINT_IMAGE)
            ptr = _read<unsigned short int>(nx, ny, fp);
        else if (data_type == IS_LINT_IMAGE)
            ptr = _read<int>(nx, ny, fp);
        else if (data_type == IS_FLOAT_IMAGE)
            ptr = _read<float>(nx, ny, fp);
        else if (data_type == IS_COMPLEX_IMAGE)
            assert(false);
        else if (data_type == IS_DOUBLE_IMAGE)
            ptr = _read<double>(nx, ny, fp);
        else if (data_type == IS_COMPLEX_DOUBLE_IMAGE)
            assert(false);
        else
            file_error++;
        fclose(fp);
        return file_error;
    }

    bool _load_calib_im_file_from_record(gen_record *g_r, int im, std::string fname)
    {
        long int start, end;
        char test[32], *st = NULL;
        FILE *fp = NULL, *fpo = NULL;
        unsigned char uch;
        int read_error = 0, write_error = 0,  i;
        size_t result;

        if (g_r == NULL || im < 0 || im >= g_r->n_bead)
            return false;

        fpo = fopen(fname.data(), "wb");
        if (fpo == NULL)
        {
            fclose(fp);
            return false;
        }

        fp = fopen(g_r->fullname, "rb+");
        if (fp == NULL)
            return false;


        start = g_r->b_r[im]->cal_im_start;
        end = (im == g_r->n_bead - 1) ? g_r->config_file_position : g_r->b_r[im + 1]->cal_im_start;
        if (end - start < 1024)
            return false;

        fseek(fp, start, SEEK_SET);      // we go to file end
        result = fread(test, sizeof(char), 32, fp);
        if (result != 32)
        {
            fclose(fp);
            fclose(fpo);
            return NULL;
        }

        st = strstr(test, "image data");
        if (st == NULL)
        {
            start += 1024;

            fseek(fp, start, SEEK_SET);

            result = fread(test, sizeof(char), 32, fp);
            st = strstr(test, "image data");

            if (st == NULL)
            {
                fclose(fp);
                fclose(fpo);
                return NULL;
            }
        }

        fseek(fp, start, SEEK_SET);      // we go to file end
        for (i = start; i < end; i++)
        {
            // we put data on 1k boundary
            if (fread(&uch, sizeof(unsigned char), 1, fp) != 1)
            {
                read_error++;
            }

            if (fwrite(&uch, sizeof(unsigned char), 1, fpo) != 1)
            {
                write_error++;
            }
        }

        fclose(fp);
        fclose(fpo);
        return true;
    }
}


// getters
namespace legacy
{
    size_t GenRecord::nbeads   () const
    { return size_t(_ptr == nullptr || _ptr->n_bead < 0 ? 0: _ptr->n_bead); }
    size_t GenRecord::nrecs    () const
    { return size_t(_ptr == nullptr || _ptr->abs_pos < 0 ? 0: _ptr->abs_pos); }
    size_t GenRecord::ncycles  () const
    {
        if(_ptr == nullptr || _ptr->abs_pos < 0)
            return 0;
        int lmin = 0, lmax = 0, lphase = 0;
        _retrieve_min_max_event_and_phases(_ptr, &lmin, &lmax, &lphase);
        return lmax-lmin+1;
    }

    bool GenRecord::readcalib(int im, std::string fname) const
    {
        if(_ptr == nullptr || _ptr->abs_pos < 0)
            return false;
        return _load_calib_im_file_from_record(_ptr, im, fname);
    }

    int GenRecord::cyclemin  () const
    {
        if(_ptr == nullptr || _ptr->abs_pos < 0)
            return 0;
        int lmin = 0, lmax = 0, lphase = 0;
        _retrieve_min_max_event_and_phases(_ptr, &lmin, &lmax, &lphase);
        return lmin;
    }

    int GenRecord::cyclemax  () const
    {
        if(_ptr == nullptr || _ptr->abs_pos < 0)
            return 0;
        int lmin = 0, lmax = 0, lphase = 0;
        _retrieve_min_max_event_and_phases(_ptr, &lmin, &lmax, &lphase);
        return lmax;
    }

    size_t GenRecord::nphases  () const
    {
        if(_ptr == nullptr || _ptr->abs_pos < 0)
            return 0;
        int lmin = 0, lmax = 0, lphase = 0;
        _retrieve_min_max_event_and_phases(_ptr, &lmin, &lmax, &lphase);
        return lphase;
    }

    void   GenRecord::cycles(int *dt) const
    {
        if(_ptr == nullptr || _ptr->abs_pos < 0)
            return;
        int lmin = 0, lmax = 0, lphase = 0;
        _retrieve_min_max_event_and_phases(_ptr, &lmin, &lmax, &lphase);

        int inds[2] = { 0, 0};
        for(int i = lmin; i <= lmax; ++i)
            for(int k = 0; k < lphase; ++k, ++dt)
            {
                int  _   = 0;

                _retrieve_image_index_of_next_point_phase(_ptr, i, k, inds, inds+1, &_);
                dt[0]   = inds[0];
                inds[0] = inds[1];
            }
    }

    template <typename T>
    void GenRecord::_get(T ** ptr, T corr, T bias, T * out) const
    {
        if(_ptr == nullptr)
            return;
        size_t psz  = size_t(_ptr->page_size);
#           define ITER(CODE)                                                   \
            for(size_t i = 0, e = nrecs(); i < e; i += psz, out += psz, ++ptr)  \
                for(size_t k = 0, ke = i+psz > e ? e-i : psz; k < ke; ++k)      \
                    out[k] = CODE ptr[0][k];
        if(corr == 1 && bias == 0)
            ITER( )
        else if(corr == 1)
            ITER(bias+)
        else if(bias == 0)
            ITER(corr*)
        else
            ITER(bias+corr*)
#           undef ITER
    }

    void   GenRecord::t     (int  * dt)  const
    { _get(_ptr->imi, 1, -_ptr->imi[0][0], dt); }

    void   GenRecord::zmagcmd(float *dt)  const
    { _get(_ptr->zmag_cmd, 1.0f, 0.0f, dt); }

    void   GenRecord::status(int *dt)  const
    { _get(_ptr->status_flag, 1, 0, dt); }

    void   GenRecord::zmag  (float *dt)  const
    { _get(_ptr->zmag, 1.0f, 0.0f, dt); }

    void   GenRecord::rot   (float *dt)  const
    { _get(_ptr->rot_mag, 1.0f, 0.0f, dt); }

    std::vector<std::vector<float>> GenRecord::vcap()  const
    {
        if(_ptr == nullptr)
            return {};
        std::vector<std::vector<float>> data(3);
        size_t   psz = size_t(_ptr->page_size);
        float ** ptr = _ptr->zmag_cmd;
        float ** zma = _ptr->zmag;
        int   ** sta = _ptr->status_flag;
        int   ** act = _ptr->action_status;
        int   ** imi = _ptr->imi;
        float    t0  = _ptr->timing_mode == 1 ? float(_ptr->imi[0][0]) : 0.0f;

#       define PARTS_MOVING   0x000000F0// 0x03F0
#       define DATA_AVERAGING 0x40000000
        float    zavg  = 0.f, vavg = 0.f;
        size_t   cnt   = 0;
        int      first = 0;
        for(size_t i = 0, e = nrecs(); i < e; i += psz, ++ptr, ++sta, ++imi, ++act, ++zma)
            for(size_t k = 0, ke = i+psz > e ? e-i : psz; k < ke; ++k)
                if(act[0][k] & DATA_AVERAGING)
                {
                    if((sta[0][k] & PARTS_MOVING) == 0)
                    {
                        if(cnt == 0)
                            first = imi[0][k];
                        zavg += zma[0][k]; 
                        vavg += ptr[0][k]; 
                        ++cnt;
                    }
                } else if(cnt)
                {
                    data[0].push_back(.5f*float(imi[0][k] + first)-t0);
                    data[1].push_back(zavg/cnt);
                    data[2].push_back(vavg/cnt);
                    cnt  = 0;
                    zavg = 0.f;
                    vavg = 0.f;
                }
                
        return data;
    }

    std::vector<std::vector<std::pair<int, float> > > GenRecord::temperatures() const
    {
        if(_ptr == nullptr)
            return {};

        std::vector<std::vector<std::pair<int, float> > > data(3);
        size_t  psz  = size_t(_ptr->page_size);
        char ** ptr  = _ptr->message;
        int  ** time = _ptr->imi;
        int     lmi  = 0;
        char    l_mes[32];
        int     t0   = _ptr->timing_mode == 1 ? _ptr->imi[0][0] : 0;

        for(size_t i = 0, e = nrecs(); i < e; i += psz, ++ptr, ++time)
            for(size_t k = 0, ke = i+psz > e ? e-i : psz; k < ke; ++k)
                if (ptr[0][k] == 0)
                {
                    if(lmi > 3 && l_mes[0] == 'T')
                    {
                        int ind     = l_mes[1] == '0' ? 0 :
                                      l_mes[1] == '1' ? 1 :
                                      l_mes[1] == '2' ? 2 :
                                      -1;
                        if(ind != -1)
                        {
                            float T = NAN;
                            sscanf(l_mes + 3, "%f", &T);
                            data[ind].push_back({time[0][k] - t0, T});
                        }
                    }

                    lmi = 0;
                }
                else if (lmi < 32)
                    l_mes[lmi++] = ptr[0][k];
        return data;
    }

    std::map<int, std::tuple<float, float, float>> GenRecord::pos()  const
    {
        decltype(this->pos()) res;
        if(_ptr == nullptr)
            ;
        else if(_ptr->SDI_mode)
        {
            size_t psz = size_t(_ptr->page_size);
            size_t e   = this->nrecs();
            auto   avg = [&](auto ** ptr)
                {
                    double cnt = 0;
                    double out = 0.;
                    for(size_t i = 0; i < e; i += psz, ++ptr)
                        for(size_t k = 0, ke = i+psz > e ? e-i : psz; k < ke; ++k)
                            if(std::isfinite(ptr[0][k]))
                            {
                                out = out *(cnt/(cnt+1)) + ptr[0][k]/(cnt+1);
                                ++cnt;
                            }
                    return float(out);
                };

            for(size_t ibead = size_t(0), ebead = _ptr->n_bead; ibead < ebead; ++ibead)
                res[ibead] = std::make_tuple(avg(_ptr->b_r[ibead]->x)*_ptr->dx+_ptr->ax,
                                             avg(_ptr->b_r[ibead]->y)*_ptr->dy+_ptr->ay,
                                             avg(_ptr->b_r[ibead]->z)*_ptr->z_cor);
        } else {
            std::smatch val;
            std::string flt = "[-+]?(?:\\d+(?:[.,]\\d*)?|[.,]\\d+)(?:[eE][-+]?\\d+)?";
            std::string tmp = "^Bead(\\d+) xcb ("+flt+") ycb ("+flt+") zcb ("+flt+") .*";
            std::regex  patt(tmp.c_str());

            std::ifstream stream(_name.c_str(), std::ios_base::in | std::ios_base::binary);

            std::string           line;
            while(std::getline(stream, line))
                if(std::regex_match(line, val, patt) && val.size() == 5)
              res[std::stoi(val[1])] = std::make_tuple(std::stof(val[2]),
                                   std::stof(val[3]),
                                   std::stof(val[4])
                                   );
            stream.close();
        }
        return res;
    }

    void   GenRecord::xbeaderr  (size_t ibead, float *dt) const
    {
        if(_ptr == nullptr || ibead >= size_t(_ptr->n_bead))
            return;
        _get(_ptr->b_r[ibead]->x_er, 1.0f, 0.0f, dt);
    }

    void   GenRecord::ybeaderr  (size_t ibead, float *dt) const
    {
        if(_ptr == nullptr || ibead >= size_t(_ptr->n_bead))
            return;
        _get(_ptr->b_r[ibead]->y_er, 1.0f, 0.0f, dt);
    }

    void   GenRecord::zbeaderr  (size_t ibead, float *dt) const
    {
        if(_ptr == nullptr || ibead >= size_t(_ptr->n_bead))
            return;
        _get(_ptr->b_r[ibead]->z_er, 1.0f, 0.0f, dt);
    }

    void   GenRecord::bead  (size_t ibead, float *dt) const
    {
        if(_ptr == nullptr || ibead >= size_t(_ptr->n_bead))
            return;
        _get(_ptr->b_r[ibead]->z, _ptr->z_cor, 0.0f, dt);
    }

    std::vector<float>  GenRecord::bead  (size_t i, int tpe) const
    {
        std::vector<float> x(nrecs());
        switch (tpe)
        {
            case 0: bead(i, x.data()); break;
            case 1: xbead(i, x.data()); break;
            case 2: ybead(i, x.data()); break;
            case 3: xbeaderr(i, x.data()); break;
            case 4: ybeaderr(i, x.data()); break;
            case 5: zbeaderr(i, x.data()); break;
        }
        return x;
    }

    void   GenRecord::xbead  (size_t ibead, float *dt) const
    {
        if(_ptr == nullptr || ibead >= size_t(_ptr->n_bead))
            return;
        _get(_ptr->b_r[ibead]->x, _ptr->dx, _ptr->ax, dt);
    }

    void   GenRecord::ybead  (size_t ibead, float *dt) const
    {
        if(_ptr == nullptr || ibead >= size_t(_ptr->n_bead))
            return;
        _get(_ptr->b_r[ibead]->y, _ptr->dy, _ptr->ay, dt);
    }

    float  GenRecord::camerafrequency() const
    { return _ptr == nullptr ? 0 : _ptr->Pico_param_record.camera_param.camera_frequency_in_Hz; }

    bool GenRecord::islost(int i) const
    {
        if(_ptr == nullptr || i < 0 || i >= _ptr->n_bead)
            return true;
        return _ptr->b_r[i]->completely_losted;
            //|| _ptr->b_r[i]->calib_im == NULL && _ptr->SDI_mode == 0;
    }

    bool GenRecord::readfov(int &nx, int &ny, int &dt, void *& ptr)
    {
        if(_ptr == nullptr)
            return true;
        return _read_mic_image(_ptr, nx, ny, dt, ptr) == 0;
    }

    void GenRecord::destroyfov(int data_type, void *& ptr)
    {
        if (data_type == IS_CHAR_IMAGE)
            delete [] ((char*) ptr);
        else if (data_type == IS_RGB_PICTURE)
            assert(false);
        else if (data_type == IS_RGBA_PICTURE)
            assert(false);
        else if (data_type == IS_RGB16_PICTURE)
            assert(false);
        else if (data_type == IS_RGBA16_PICTURE)
            assert(false);
        else if (data_type == IS_INT_IMAGE)
            delete [] ((short int*) ptr);
        else if (data_type == IS_UINT_IMAGE)
            delete [] ((unsigned short int*) ptr);
        else if (data_type == IS_LINT_IMAGE)
            delete [] ((int*) ptr);
        else if (data_type == IS_FLOAT_IMAGE)
            delete [] ((float*) ptr);
        else if (data_type == IS_COMPLEX_IMAGE)
            assert(false);
        else if (data_type == IS_DOUBLE_IMAGE)
            delete [] ((double*) ptr);
        else if (data_type == IS_COMPLEX_DOUBLE_IMAGE)
            assert(false);
        ptr = nullptr;
    }

    std::tuple<float, float, float, float> GenRecord::dimensions() const
    { return std::make_tuple(_ptr->dx, _ptr->ax, _ptr->dy, _ptr->ay); }

    bool GenRecord::sdi() const
    { return _ptr != nullptr && _ptr->SDI_mode != 0; }

    void GenRecord::open(std::string x)
    {
        close();
        char tmp[2048];
        strncpy(tmp, x.c_str(), sizeof(tmp));
        _ptr  = load(tmp);
        _name = x;
    }

}
