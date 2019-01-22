#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cmath>
#if (__GNUC__ == 8 && __GNUC_MINOR__ == 2)
# pragma GCC diagnostic push
# pragma GCC diagnostic ignored "-Wstringop-truncation"
# pragma GCC diagnostic ignored "-Wformat-truncation"
#endif
#ifdef _MSC_VER
# pragma warning( disable : 4996 4244 4267 4305 4800 4477 4653)
#endif
#include "legacy/legacygr.h"

namespace legacy { namespace { // unitset
    long    counter = 0, n_error = 0;
    float   abslow, dx;     /* offset and scale for automatic abscissas */
    int     absf;           /* flag for automatic abscissas */
    int     sizef = 0;          /* flag for changing plot size */
    int     aflag = 0;
    char    plt_data_path[512];
    # define BUILD_COLOR(r,g,b)		(((b)&0xff)<<16)+(((g)&0xff)<<8)+((r)&0xff)
    int	Black			=	0;
    int	Blue			= BUILD_COLOR(  0,  0,128); 
    int	Green			= BUILD_COLOR(  0,128,  0);
    int	Cyan			= BUILD_COLOR(  0,128,128);
    int	Red				= BUILD_COLOR(128,  0,  0);
    int	Magenta			= BUILD_COLOR(128,  0,128);
    int	Brown			= BUILD_COLOR(128,128,  0);
    int	Lightgray		= BUILD_COLOR(171,171,171);
    int	Darkgray		= BUILD_COLOR( 85, 85, 85);
    int	Lightblue		= BUILD_COLOR( 64, 64,255);
    int	Lightgreen		= BUILD_COLOR( 64,255, 64);
    int	Lightcyan		= BUILD_COLOR(  0,255,255);
    int	Lightred		= BUILD_COLOR(255, 64, 64);
    int	Lightmagenta	= BUILD_COLOR(255,  0,255);
    int	Yellow			= BUILD_COLOR(255,255,  0);
    int	White 			= BUILD_COLOR(255,255,255);

    # define 	WHITE_LABEL		16
    # define B_LINE 	65536
    # define CMID		27
    # define MAX_ERROR 	20
    # define OP_SIZE 	32
    # define CRT_Z 		26
    # define GR_SIZE	16384
    # define Mystrdup(src)	((src) == NULL) ? NULL : strdup((src))
    # define    X_AXIS      2304    /* 2048 + 256 */
    # define    Y_AXIS      2048
    char    *Mystrdupre(char *dest, const  char *src)
    {
        if (dest != NULL)
        {
            free(dest);
        }

        if (src != NULL && strlen(src) > 0)
        {
            dest = strdup(src);
        }
        else
        {
            dest = NULL;
        }

        return dest;
    }

    # define MAX_DATA 		16
    # define NOAXES		0000002
    # define AXES_PRIME	0000400
    # define TRIM		0001000
    # define XLOG		0002000
    # define YLOG		0004000
    # define CROSS		0020000
    
    # define GRID		TRIM + NOAXES + AXES_PRIME
    
    # define X_NUM		0000001
    # define Y_NUM		0000002
    # define X_LIM		0000004			/* axis limit is not imposed */
    # define Y_LIM		0000010
    
    # define 	IS_SPECIAL		32
    # define 	IS_DATA_SET		2048
    # define 	IS_PLOT_LABEL		4096
    # define 	IS_X_UNIT_SET		16
    # define 	IS_Y_UNIT_SET		17
    # define 	IS_T_UNIT_SET		19
    
    # define 	ABS_COORD		0
    # define 	USR_COORD		1
    # define 	VERT_LABEL_USR		2
    # define 	VERT_LABEL_ABS		3
    
    # define 	IS_TERRA		12
    # define 	IS_GIGA			9
    # define 	IS_MEGA			6
    # define 	IS_KILO			3
    # define 	IS_MILLI		-3
    # define 	IS_MICRO		-6
    # define 	IS_NANO			-9
    # define 	IS_PICO			-12
    # define 	IS_FEMTO		-15
    
    # define 	IS_VOLT			256
    # define 	IS_AMPERE		512
    # define 	IS_METER		1024
    # define 	IS_NEWTON		2048
    # define 	IS_SECOND		4096
    # define 	IS_GRAMME		8192
    # define 	IS_GAUSS		16384
    # define 	IS_OHM			32768
    # define 	IS_RAW_U		-128 		/* raw data */

    struct unit_set
    {
        int type, sub_type, axis;	/* identifier */
        float ax, dx;			/* the offset and increment */
        char	decade;			/* the decade value*/
        char	mode;			/* log or a^2 */
        char *name;			/* the text of it */
    };

    unit_set *build_unit_set(int type, float ax, float dx, char decade, char mode, char *name)
    {
        unit_set *uns;
        
        uns = (unit_set*)calloc(1,sizeof(unit_set));
        if ( uns == NULL )		return NULL;
        uns->type = type;
        uns->ax = ax;
        uns->dx = dx;
        uns->decade = decade;
        uns->mode = mode;
        if (name == NULL)      uns->name = NULL;
        else if (name != NULL && strncmp(name,"no_name",7) == 0 ) 
          uns->name = NULL;
        else	uns->name = Mystrdup(name);
        return uns;
    }

    int 	free_unit_set(unit_set *uns)
    {
        if (uns == NULL)	return 1;
        if (uns->name != NULL) 	free(uns->name);
        free(uns);	uns = NULL;
        return 0;
    }

    int	unit_to_type(char *unit, int *type, int *decade)
    {
        int t, d;
        int adv = 1;
        
        if (unit == NULL)	return 1;
        if (strncmp(unit,"\\mu ",4) == 0 )	
        {
            d = IS_MICRO;
            unit += 4;
        }
        else
        {
            switch (unit[0])
            {
                case 'T'  :		d = IS_TERRA;		break;
                case 'G' :		d = IS_GIGA;		break;
                case 'M' :		d = IS_MEGA;		break;
                case 'K' :		d = IS_KILO;		break;
                case 'm' :		d = IS_MILLI;		break;
                case 'n' : 		d = IS_NANO;		break;
                case 'p' :		d = IS_PICO;		break;
                case 'f' :		d = IS_FEMTO;		break;
                default :		adv = 0;	d = 0;	break;
            };
            unit += adv;
        }
        if (strncmp(unit,"\\Omega ",6 )== 0 )	
        {
            t = IS_OHM;
        }	
        else
        {
            switch (unit[0])
            {
                case 'V' :	t = IS_VOLT;		break;
                case 'A' :	t = IS_AMPERE;		break;
                case 'm' :	t = IS_METER;		break;
                case 'N' :	t = IS_NEWTON;		break;
                case 's' :	t = IS_SECOND;		break;
                case 'g' :	t = IS_GRAMME;		break;
                case 'G' :	t = IS_GAUSS;		break;
                default :	return 1;		break;
            };
        }
        *type = t;
        *decade = d;
        return 0;
    }
}}

namespace legacy { namespace { // ds
    struct ErrorInFile {};
    char const * Out_Of_Memory = nullptr;
    char const * Wrong_Argument = nullptr;
    [[noreturn]] void xvin_ptr_error(char const *) { throw ErrorInFile(); }
    [[noreturn]] void error_in_file( char *, ...) { throw ErrorInFile(); }

    int     data_color[4] =  {Yellow, Lightgreen, Lightred, Lightblue};
    int     max_data_color = 4;

    struct plot_label
    {
        int type;			/* absolute or user defined */
        float xla, yla;			/* the position of label */
        char *text;			/* the text of it */
        struct box *b;			/* the plot box */
    };

    struct data_set
    {
        int nx, ny, type;		/* number of x and y data */
        int mx, my;			/* size alloc for x and y */
        float *xd, *yd;			/* the x and y data */
        float *xe, *ye;			/* the x and y error on data, symetric if xeb and yev are not defined, error above xd otherwise, (max value for boxplot)*/
        // TODO EXPORT DATA IN GR
        float *xed, *yed;       /* the x and y error on data, below the point (min value for boxplot)*/
        float *xbu, *ybu;   /* the x and y upperside of the box for boxplot, if xbd and ybd is not define, the box will be symetric */
        float *xbd, *ybd;    /* the x and y downside of the box for boxplot */
        float boxplot_width;
        // END TODO
        char *symb;			/* the symbol to plot */
        int m;				/* the line style */
        int color;			/* the drawing color */
        time_t time;			/* date of creation */ /* long int changed into time_t 2006/11/10, NG */
        char *source;
        char *history;
        char *treatement;
        char **special;
        int n_special, m_special;
        struct plot_label **lab;	/* labelling in the plot attached to ds */
        int n_lab, m_lab;		/* the last and size*/
        int need_to_refresh;
        double record_duration;         /* duration of data acquisition in micro seconds */
        long long recordata_settart;         /* start of duration of data */
        int invisible;                  /* if set make the dataset invisible, but data is still there */
        int user_ispare[16];
        float user_fspare[16];
        float src_parameter[8];        // numerical value of parameter characterizing data (ex. temperature ...)
        char *src_parameter_type[8];   // the description of these parameters
    };

    int free_data_set(data_set *ds)
    {
        int i;

        if (ds == NULL)
        {
            return 1;
        }

        if (ds->xd != NULL)
        {
            free(ds->xd);
            ds->xd = NULL;
        }

        if (ds->yd != NULL)
        {
            free(ds->yd);
            ds->yd = NULL;
        }

        if (ds->xe != NULL)
        {
            free(ds->xe);
            ds->xe = NULL;
        }

        if (ds->ye != NULL)
        {
            free(ds->ye);
            ds->ye = NULL;
        }

        if (ds->xed != NULL)
        {
            free(ds->xed);
            ds->xed = NULL;
        }

        if (ds->yed != NULL)
        {
            free(ds->yed);
            ds->yed = NULL;
        }

        if (ds->xbu != NULL)
        {
            free(ds->xbu);
            ds->xbu = NULL;
        }

        if (ds->ybu != NULL)
        {
            free(ds->ybu);
            ds->yed = NULL;
        }

        if (ds->xbd != NULL)
        {
            free(ds->xbd);
            ds->xbd = NULL;
        }

        if (ds->ybd != NULL)
        {
            free(ds->ybd);
            ds->ybd = NULL;
        }

        if (ds->symb != NULL)
        {
            free(ds->symb);
            ds->symb = NULL;
        }

        if (ds->source != NULL)
        {
            free(ds->source);
            ds->source = NULL;
        }

        if (ds->history != NULL)
        {
            free(ds->history);
            ds->history = NULL;
        }

        if (ds->treatement != NULL)
        {
            free(ds->treatement);
            ds->treatement = NULL;
        }

        if (ds->special != NULL)
        {
            for (i = 0 ; i < ds->n_special ; i++)
                if (ds->special[i] != NULL)
                {
                    free(ds->special[i]);
                    ds->special[i] = NULL;
                }

            free(ds->special);
            ds->special = NULL;
        }

        for (i = 0 ; i < ds->n_lab ; i++)
        {
            if (ds->lab[i]->text != NULL)
            {
                free(ds->lab[i]->text);
                ds->lab[i]->text = NULL;
            }

            if (ds->lab[i] != NULL)
            {
                free(ds->lab[i]);
                ds->lab[i] = NULL;
            }
        }

        if (ds->lab)
        {
            free(ds->lab);
            ds->lab = NULL;
        }

        for (i = 0 ; i < 8 ; i++)
        {
            if (ds->src_parameter_type[i] != NULL)
            {
                free(ds->src_parameter_type[i]);
                ds->src_parameter_type[i] = NULL;
            }
        }

        free(ds);
        ds = NULL;
        return 0;
    }

    int add_to_data_set(data_set *ds, int type, void *stuff)
    {
        if (stuff == NULL || ds == NULL)
        {
            xvin_ptr_error(Wrong_Argument);
        }
        else if (type == IS_SPECIAL && strlen((char *)stuff) > 0)
        {
            if (ds->n_special >=  ds->m_special)
            {
                ds->m_special++;
                ds->special = (char **)realloc
                              (ds->special, ds->m_special * sizeof(char *));

                if (ds->special == NULL)
                {
                    xvin_ptr_error(Out_Of_Memory);
                }
            }

            ds->special[ds->n_special] = strdup((char *)stuff);
            ds->n_special++;
        }
        else if (type == IS_PLOT_LABEL)
        {
            if (ds->n_lab >= ds->m_lab)
            {
                ds->m_lab += MAX_DATA;
                ds->lab = (plot_label **)realloc(ds->lab, ds->m_lab * sizeof(plot_label *));

                if (ds->lab == NULL)
                {
                    xvin_ptr_error(Out_Of_Memory);
                }
            }

            if (((plot_label *)stuff)->text != NULL)   /* no empty label */
            {
                ds->lab[ds->n_lab] = (plot_label *)stuff;
                ds->n_lab++;
            }

            ds->need_to_refresh = 1;
        }

        return 0;
    }

    data_set *build_data_set(int nx, int ny)
    {
        int i;
        data_set *ds;

        if (nx <= 0 || ny <= 0)
        {
            return NULL;
        }

        ds = (data_set *)calloc(1, sizeof(data_set));

        if (ds == NULL)
        {
            xvin_ptr_error(Out_Of_Memory);
        }

        ds->xd = (float *)calloc(nx, sizeof(float));
        ds->yd = (float *)calloc(ny, sizeof(float));

        if (ds->xd == NULL || ds->yd == NULL)
        {
            free_data_set(ds);
            xvin_ptr_error(Out_Of_Memory);
        }

        ds->mx = nx;
        ds->my = ny;
        ds->m = 1;
        ds->xe = ds->ye = NULL;
        ds->xed = ds->yed = NULL;
        ds->xbu = ds->ybu = NULL;
        ds->xbd = ds->ybd = NULL;
        ds->color = 1;
        ds->n_special = ds->m_special = 0;
        ds->special = NULL;
        ds->symb = NULL;
        ds->source = NULL;
        ds->history = NULL;
        ds->treatement = NULL;
        ds->special = NULL;
        ds->lab = (plot_label **)calloc(MAX_DATA, sizeof(plot_label *));
        ds->boxplot_width = 1;

        if (ds->lab == NULL)
        {
            free_data_set(ds);
            xvin_ptr_error(Out_Of_Memory);
        }

        ds->m_lab = MAX_DATA;
        // following line added 2007/10/16, N.G.:
        ds->nx = nx;
        ds->ny = ny;

        for (i = 0 ; i < 8 ; i++)
        {
            ds->src_parameter_type[i] = NULL;
            ds->src_parameter[i] = 0;
        }

        ds->invisible = 0;
        return ds;
    }

    data_set *build_adjust_data_set(data_set *ds, int nx, int ny)
    {
        if (ds == NULL || nx <= 0 || ny <= 0)
        {
            return (build_data_set(nx, ny));
        }

        if (nx < ds->mx || ny < ds->my)
        {
            ds->nx = nx;
            ds->ny  = ny;
            return ds;
        }

        ds->xd = (float *)realloc(ds->xd, nx * sizeof(float));
        ds->yd = (float *)realloc(ds->yd, ny * sizeof(float));

        if (ds->xd == NULL || ds->yd == NULL)
        {
            xvin_ptr_error(Out_Of_Memory);
        }

        ds->mx = nx;
        ds->my = ny;

        if (ds->xe != NULL)
        {
            ds->xe = (float *)realloc(ds->xe, nx * sizeof(float));

            if (ds->xe == NULL)
            {
                xvin_ptr_error(Out_Of_Memory);
            }
        }

        if (ds->ye != NULL)
        {
            ds->ye = (float *)realloc(ds->ye, ny * sizeof(float));

            if (ds->ye == NULL)
            {
                xvin_ptr_error(Out_Of_Memory);
            }
        }

        if (ds->xed != NULL)
        {
            ds->xed = (float *)realloc(ds->xed, nx * sizeof(float));

            if (ds->xed == NULL)
            {
                xvin_ptr_error(Out_Of_Memory);
            }
        }

        if (ds->yed != NULL)
        {
            ds->yed = (float *)realloc(ds->yed, ny * sizeof(float));

            if (ds->yed == NULL)
            {
                xvin_ptr_error(Out_Of_Memory);
            }
        }

        if (ds->xbu != NULL)
        {
            ds->xbu = (float *)realloc(ds->xbu, nx * sizeof(float));

            if (ds->xbu == NULL)
            {
                xvin_ptr_error(Out_Of_Memory);
            }
        }

        if (ds->ybu != NULL)
        {
            ds->ybu = (float *)realloc(ds->ybu, ny * sizeof(float));

            if (ds->ybu == NULL)
            {
                xvin_ptr_error(Out_Of_Memory);
            }
        }

        if (ds->xbd != NULL)
        {
            ds->xbd = (float *)realloc(ds->xbd, nx * sizeof(float));

            if (ds->xbd == NULL)
            {
                xvin_ptr_error(Out_Of_Memory);
            }
        }

        if (ds->ybd != NULL)
        {
            ds->ybd = (float *)realloc(ds->ybd, ny * sizeof(float));

            if (ds->ybd == NULL)
            {
                xvin_ptr_error(Out_Of_Memory);
            }
        }

        return ds;
    }

    data_set *alloc_data_set_y_error(data_set *ds)
    {
        if (ds == NULL)
        {
            xvin_ptr_error(Wrong_Argument);
        }

        if (ds->ye != NULL)
        {
            return ds;
        }

        ds->ye = (float *)calloc(ds->my, sizeof(float));

        if (ds->ye == NULL)
        {
            xvin_ptr_error(Out_Of_Memory);
        }

        return ds;
    }

    data_set *alloc_data_set_x_error(data_set *ds)
    {
        if (ds == NULL)
        {
            xvin_ptr_error(Wrong_Argument);
        }

        if (ds->xe != NULL)
        {
            return ds;
        }

        ds->xe = (float *)calloc(ds->mx, sizeof(float));

        if (ds->xe == NULL)
        {
            xvin_ptr_error(Out_Of_Memory);
        }

        return ds;
    }

    data_set *duplicate_data_set(const data_set *src, data_set *dest)
    {
        int i, j;
        plot_label *sp, *dp;
        int n_min, m_min;

        if (src == NULL)
        {
            xvin_ptr_error(Wrong_Argument);
        }

        n_min = (src->nx < src->ny) ? src->nx : src->ny;
        m_min = (src->mx < src->my) ? src->mx : src->my;
        m_min = (m_min <= 0) ? 16 : m_min;

        if ((dest == NULL) || (dest->mx < n_min) || (dest->my < n_min))
        {
            if (n_min > 0)
            {
                dest = build_adjust_data_set(dest, n_min, n_min);
            }
            else
            {
                dest = build_adjust_data_set(dest, m_min, m_min);

                if (dest != NULL)
                {
                    dest->nx = dest->ny = n_min;
                }
            }

            if (dest == NULL)
            {
                xvin_ptr_error(Out_Of_Memory);
            }
        }

        if (src->xe != NULL && dest->xe == NULL)
        {
            if (src->nx > 0)
            {
                dest->xe = (float *)realloc(dest->xe, src->nx * sizeof(float));
            }
            else
            {
                dest->xe = (float *)realloc(dest->xe, m_min * sizeof(float));
            }

            if (dest->xe == NULL)
            {
                free_data_set(dest);
                xvin_ptr_error(Out_Of_Memory);
            }
        }

        if (src->ye != NULL && dest->ye == NULL)
        {
            if (src->ny > 0)
            {
                dest->ye = (float *)realloc(dest->ye, src->ny * sizeof(float));
            }
            else
            {
                dest->ye = (float *)realloc(dest->ye, m_min * sizeof(float));
            }

            if (dest->ye == NULL)
            {
                free_data_set(dest);
                xvin_ptr_error(Out_Of_Memory);
            }
        }

        if (src->xed != NULL && dest->xed == NULL)
        {
            if (src->nx > 0)
            {
                dest->xed = (float *)realloc(dest->xed, src->nx * sizeof(float));
            }
            else
            {
                dest->xed = (float *)realloc(dest->xed, m_min * sizeof(float));
            }

            if (dest->xed == NULL)
            {
                free_data_set(dest);
                xvin_ptr_error(Out_Of_Memory);
            }
        }

        if (src->yed != NULL && dest->yed == NULL)
        {
            if (src->ny > 0)
            {
                dest->yed = (float *)realloc(dest->yed, src->ny * sizeof(float));
            }
            else
            {
                dest->yed = (float *)realloc(dest->yed, m_min * sizeof(float));
            }

            if (dest->yed == NULL)
            {
                free_data_set(dest);
                xvin_ptr_error(Out_Of_Memory);
            }
        }

        if (src->xbu != NULL && dest->xbu == NULL)
        {
            if (src->nx > 0)
            {
                dest->xbu = (float *)realloc(dest->xbu, src->nx * sizeof(float));
            }
            else
            {
                dest->xbu = (float *)realloc(dest->xbu, m_min * sizeof(float));
            }

            if (dest->xbu == NULL)
            {
                free_data_set(dest);
                xvin_ptr_error(Out_Of_Memory);
            }
        }

        if (src->ybu != NULL && dest->ybu == NULL)
        {
            if (src->ny > 0)
            {
                dest->ybu = (float *)realloc(dest->ybu, src->ny * sizeof(float));
            }
            else
            {
                dest->ybu = (float *)realloc(dest->ybu, m_min * sizeof(float));
            }

            if (dest->ybu == NULL)
            {
                free_data_set(dest);
                xvin_ptr_error(Out_Of_Memory);
            }
        }

        if (src->xbd != NULL && dest->xbd == NULL)
        {
            if (src->nx > 0)
            {
                dest->xbd = (float *)realloc(dest->xbd, src->nx * sizeof(float));
            }
            else
            {
                dest->xbd = (float *)realloc(dest->xbd, m_min * sizeof(float));
            }

            if (dest->xbd == NULL)
            {
                free_data_set(dest);
                xvin_ptr_error(Out_Of_Memory);
            }
        }

        if (src->ybd != NULL && dest->ybd == NULL)
        {
            if (src->ny > 0)
            {
                dest->ybd = (float *)realloc(dest->ybd, src->ny * sizeof(float));
            }
            else
            {
                dest->ybd = (float *)realloc(dest->ybd, m_min * sizeof(float));
            }

            if (dest->ybd == NULL)
            {
                free_data_set(dest);
                xvin_ptr_error(Out_Of_Memory);
            }
        }

        dest->boxplot_width = src->boxplot_width;
        dest->symb = Mystrdup(src->symb);
        dest->m = src->m;
        dest->color = src->color;
        dest->time = src->time;
        dest->nx = n_min;
        dest->ny = n_min;

        for (j = 0 ; j < n_min ; j++)
        {
            dest->xd[j] = src->xd[j];
            dest->yd[j] = src->yd[j];
        }

        if (src->xe != NULL)
        {
            for (j = 0 ; j < dest->nx ; j++)
            {
                dest->xe[j] = src->xe[j];
            }
        }

        if (src->ye != NULL)
        {
            for (j = 0 ; j < dest->ny ; j++)
            {
                dest->ye[j] = src->ye[j];
            }
        }

        if (src->xed != NULL)
        {
            for (j = 0 ; j < dest->nx ; j++)
            {
                dest->xed[j] = src->xed[j];
            }
        }

        if (src->yed != NULL)
        {
            for (j = 0 ; j < dest->ny ; j++)
            {
                dest->yed[j] = src->yed[j];
            }
        }

        if (src->xbu != NULL)
        {
            for (j = 0 ; j < dest->nx ; j++)
            {
                dest->xbu[j] = src->xbu[j];
            }
        }

        if (src->ybu != NULL)
        {
            for (j = 0 ; j < dest->ny ; j++)
            {
                dest->ybu[j] = src->ybu[j];
            }
        }

        if (src->xbd != NULL)
        {
            for (j = 0 ; j < dest->nx ; j++)
            {
                dest->xbd[j] = src->xbd[j];
            }
        }

        if (src->ybd != NULL)
        {
            for (j = 0 ; j < dest->ny ; j++)
            {
                dest->ybd[j] = src->ybd[j];
            }
        }

        dest->boxplot_width = src->boxplot_width;
        dest->source = Mystrdup(src->source);
        dest->history = Mystrdup(src->history);
        dest->treatement = Mystrdup(src->treatement);

        if (src->special != NULL)
        {
            for (i = 0 ; i < src->n_special ; i++)
            {
                add_to_data_set(dest, IS_SPECIAL, (void *)(src->special[i]));
            }
        }

        for (i = 0 ; i < src->n_lab ; i++)
        {
            sp = src->lab[i];
            dp = (plot_label *)calloc(1, sizeof(plot_label));

            if (dp == NULL)
            {
                return NULL;
            }

            *dp = *sp;
            dp->text = Mystrdup(sp->text);

            if (add_to_data_set(dest, IS_PLOT_LABEL, (void *)dp))
            {
                return NULL;
            }
        }

        for (i = 0 ; i < 16 ; i++)
        {
            dest->user_ispare[i] = src->user_ispare[i];
            dest->user_fspare[i] = src->user_fspare[i];
        }
        for (i = 0 ; i < 8 ; i++)
        {
            dest->src_parameter[i] = src->src_parameter[i];

            if (src->src_parameter_type[i] != NULL && strlen(src->src_parameter_type[i]) > 0)
            {
                dest->src_parameter_type[i] = strdup(src->src_parameter_type[i]);
            }
        }

        return dest;
    }

    int push_plot_label_in_ds(data_set *ds, float tx, float ty, char *label, int type)
    {
        plot_label *pl;

        if (ds == NULL || label == NULL || strlen(label) < 1)
        {
            return 1;
        }

        pl = (plot_label *)calloc(1, sizeof(struct plot_label));

        if (pl == NULL)
        {
            fprintf(stderr, "realloc error \n");
            exit(1);
        }

        pl->xla = tx;
        pl->yla = ty;
        pl->text = (char *)strdup(label);
        pl->type = type;

        if (pl->text == NULL)
        {
            fprintf(stderr, "strdup error \n");
            return 1; //exit(1);
        }

        return add_to_data_set(ds, IS_PLOT_LABEL, (void *)pl);
    }
}}

namespace legacy {
    struct one_plot
    {
        int type;
        char *filename, *dir, *title, *x_title, *y_title;
        char *x_prime_title, *y_prime_title;
        char *x_prefix, *y_prefix, *t_prefix, *x_unit, *y_unit, *t_unit;
        float width, height, right, up;
        float ax, dx, ay, dy, at, dt;
        int iopt, iopt2;
        float tick_len, tick_len_x, tick_len_y;
        float x_lo, x_hi, y_lo, y_hi;
        struct data_set **dat;      /* the real data */
        int n_dat, m_dat;       /* the number of data set*/
        int cur_dat;            /* the current one */
        struct plot_label **lab;    /* labelling in the plot */
        int n_lab, m_lab;       /* the last and size*/
        unit_set    **xu;           /* x unit set */
        int n_xu, m_xu, c_xu,  c_xu_p;
        unit_set    **yu;           /* y unit set */
        int n_yu, m_yu, c_yu,  c_yu_p;
        unit_set    **tu;           /* t unit set (associated with index) */
        int n_tu, m_tu, c_tu, c_tu_p;
        int need_to_refresh;
        int data_changing;
        int transfering_data_to_box;
        int user_id;                  /* a user identifier */
        bool read_only; /* can't be removed by user interface */
        int user_ispare[16];
        float user_fspare[16];
    };
}

namespace legacy { namespace {
    constexpr int I_F_SIZE = 8;
    struct
    {
        int n_line;
        char const * filename;
        FILE *fpi;
    } i_f[I_F_SIZE];
    int cur_i_f = 0;


    int add_one_plot_data (one_plot *op, int type, void *stuff)
    {
        int i = 0;
        data_set *ds;

        if (stuff == NULL || op == NULL)
            xvin_ptr_error(Wrong_Argument);
        if (type == IS_DATA_SET)
        {
            if (op->n_dat >= op->m_dat )
            {
                op->m_dat += MAX_DATA;
                op->dat = (data_set**)realloc(op->dat,op->m_dat*sizeof(data_set*));
                if (op->dat == NULL)	xvin_ptr_error(Out_Of_Memory);
            }
            op->dat[op->n_dat] = (data_set*)stuff;
            ((data_set*)stuff)->color=data_color[(op->n_dat)%max_data_color];
            op->n_dat++;
            op->need_to_refresh = 1;
        }
        else if (type == IS_SPECIAL)
        {
            ds = op->dat[op->cur_dat];
            return add_to_data_set(ds, type, stuff);
        }
        else if (type == IS_PLOT_LABEL)
        {
            if (op->n_lab >= op->m_lab )
            {
                op->m_lab += MAX_DATA;
                op->lab = (plot_label**)realloc(op->lab,op->m_lab*sizeof(plot_label*));
                if (op->lab == NULL)	xvin_ptr_error(Out_Of_Memory);
            }
            if (((plot_label*)stuff)->text != NULL)	/* no empty label */
            {
                op->lab[op->n_lab] = (plot_label*)stuff;
                op->n_lab++;
            }
            op->need_to_refresh = 1;
        }
        else if (type == IS_X_UNIT_SET)
        {
            if (op->n_xu >= op->m_xu )
            {
                op->m_xu += MAX_DATA;
                op->xu = (unit_set**)realloc(op->xu,op->m_xu*sizeof(unit_set*));
                if (op->xu == NULL)		xvin_ptr_error(Out_Of_Memory);
            }
            op->xu[op->n_xu] = (unit_set*)stuff;
            ((unit_set*)stuff)->axis = IS_X_UNIT_SET;
            op->n_xu++;
            op->need_to_refresh = 1;
        }
        else if (type == IS_Y_UNIT_SET)
        {
            if (op->n_yu >= op->m_yu )
            {
                op->m_yu += MAX_DATA;
                op->yu = (unit_set**)realloc(op->yu,op->m_yu*sizeof(unit_set*));
                if (op->yu == NULL)		xvin_ptr_error(Out_Of_Memory);
            }
            op->yu[op->n_yu] = (unit_set*)stuff;
            ((unit_set*)stuff)->axis = IS_Y_UNIT_SET;
            op->n_yu++;
            op->need_to_refresh = 1;
        }
        else if (type == IS_T_UNIT_SET)
        {
            if (op->n_tu >= op->m_tu )
            {
                op->m_tu += MAX_DATA;
                op->tu = (unit_set**)realloc(op->tu,op->m_tu*sizeof(unit_set*));
                if (op->tu == NULL)		xvin_ptr_error(Out_Of_Memory);
            }
            op->tu[op->n_tu] = (unit_set*)stuff;
            ((unit_set*)stuff)->axis = IS_T_UNIT_SET;
            op->n_tu++;
            op->need_to_refresh = 1;
        }
        else 	i = 1;
        return i;
    }

    int init_data_set(one_plot *op)
    {
        data_set *ds;

        if (op == NULL)  return 1;
        if (op->n_dat > 0)
        {
            ds = op->dat[op->n_dat - 1];
            if (ds->nx == 0 || ds->ny == 0)       return 0;
        }
        ds = build_adjust_data_set(NULL, GR_SIZE, GR_SIZE);
        if (ds == NULL)       return 1;
        ds->nx = 0;
        ds->ny = 0;
        add_one_plot_data(op, IS_DATA_SET, (void *)ds);
        return 0;
    }

    int push_new_data(one_plot *op, float tx, float ty)
    {
        data_set *ds;

        if (op == NULL)  return 1;
        if (op->n_dat == 0)   if (init_data_set(op)) return 1;
        ds = op->dat[op->n_dat - 1];
        if ( ds->nx >= ds->mx || ds->ny >= ds->my)
        {
            ds = build_adjust_data_set(ds, ds->mx + GR_SIZE, ds->my + GR_SIZE);
            if (ds == NULL)       return 1;
        }
        ds->xd[ds->nx] = tx;
        ds->yd[ds->ny] = ty;
        ds->nx++;
        ds->ny++;
        return 0;
    }

    int close_data_set(one_plot *op)
    {
        data_set *ds, *dd;

        if (op == NULL)  return 1;
        if (op->n_dat == 0)           return 1;
        ds = op->dat[op->n_dat - 1];
        if (ds->nx == 0 || ds->ny == 0)       return 1;
        dd = duplicate_data_set(ds, NULL);
        if (dd == NULL)               return 1;
        dd->time = ds->time;
        op->dat[op->n_dat - 1] = dd;
        free_data_set(ds);
        return 0;
    }

    char *get_next_line(char *line)
    {
        char *c = NULL;
        int get_out = 0;
        
        do
        {
            get_out = 0;
            i_f[cur_i_f].n_line++;
            c = fgets(line,B_LINE,i_f[cur_i_f].fpi);
            if ( c == NULL)			get_out = 0;
            else if (strlen(c) == 1)	// added 2005-10-04, to compensate from MacOS behavior
                {	if (c[0]==10) 	get_out = 1;	// only if a blank line is encountered we continue
                    else			return(NULL);	// any other single character announces the binary region
                }
            else if (c[0]==26) return(NULL); // added 2006-03-04, for Linux
        } while(get_out);
        return(c); 
    }

    int get_label(char **c1, char **c2, char *line)
    {
        int j = 0;
        int  k = 0, out_loop = 1;
        char  ch = '"', last_ch = 0;

        if (c1 == NULL || c2 == NULL || line == NULL)  return -2;

        (*c1)++;
        while ( out_loop ) /* looking for label end */
        {
            if((*c1)[j] == 0)	/* label extend to next line */
            {
                if (((*c1) = get_next_line(line)) == NULL )
                    error_in_file("EOF reached before label ended");
                j=0;
            }
            if ( (*c1)[j] == 0) 				out_loop = 0;
            else if ( ((*c1)[j] == ch) && (last_ch != 92))	out_loop = 0;
            else
            {
                last_ch = (*c1)[j];
                (*c2)[k++] = (*c1)[j++];
            }
            if ( k >= B_LINE )
                error_in_file("this label is too long !...\n%s",(*c2));
        }
        (*c2)[k]=0;
        (*c1) = (*c1)+j+1;
        return (k);
    }

    int gr_numb(float *np, int *argcp, char ***argvp)
    {
        int i;

        if (*argcp <= 1)		return(0);
        i = sscanf((*argvp)[1],"%f",np);
        (*argcp)--;
        (*argvp)++;
        return(i);
    }

    int gr_numbi(int *np, int *argcp, char ***argvp)
    {
        int i;

        if (*argcp <= 1)		return(0);
        i = sscanf((*argvp)[1],"%d",np);
        (*argcp)--;
        (*argvp)++;
        return(i);
    }

    int push_bin_float_data_z(one_plot *op, char const *filename, int offset, int nx)
    {
        int i, j;
        char ch;
        int ret = 0;
        size_t len;
        FILE *binfp;
        data_set *ds = NULL;
        static char previous_file[512];
        static int first = 1;
        static long int cz = 0;

        if (op == NULL)  return 1;
        binfp = fopen (filename, "rb");
        if ( binfp == NULL )
            error_in_file ("%s binary file not found!...  \n", (filename));

        if (first)
        {
            strncpy(previous_file, filename, sizeof(previous_file));
            first = 0;
        }
        len = strlen(filename);
        len = (len > strlen(previous_file)) ? strlen(previous_file) : len;
        if (cz == 0 || strncmp(previous_file, filename, len) != 0 )
        {
            strncpy(previous_file, filename, sizeof(previous_file));
            while (fread (&ch, sizeof (char), 1, binfp) == 1 && ch != CRT_Z);
            cz = ftell(binfp);
            fseek(binfp, offset, SEEK_CUR);
        }
        else fseek(binfp, cz + offset, SEEK_SET);

        if (op->n_dat == 0)   if (init_data_set(op)) return 1;
        ds = op->dat[op->n_dat - 1];
        if ( nx >= ds->mx || nx >= ds->my)
            ds = build_adjust_data_set(ds, nx, nx);
        if (ds == NULL)
        {
            fclose(binfp);
            error_in_file ("could not create data set in binary input file \n%s \n", (filename));
        }
        if ( absf == 0 )
        {
            if (fread (ds->xd, sizeof(float), nx, binfp) != (size_t) nx)
                error_in_file ("could not read x binary data in file \n%s \n", (filename));
            if (fread (ds->yd, sizeof(float), nx, binfp) != (size_t) nx)
                error_in_file ("could not read y binary data in file \n%s \n", (filename));

#ifdef XV_MAC
#ifdef MAC_POWERPC
            swap_bytes(ds->xd, nx, sizeof(float));
            swap_bytes(ds->yd, nx, sizeof(float));
#endif
#endif
            for (i = j = 0; i < nx; i++)
                j = (std::isnan(ds->yd[i]) || std::isnan(ds->xd[i])) ? j + 1 : j;

        }
        else if ( absf == 1 || absf == 2 )
        {
            if (fread (ds->yd, sizeof(float), nx, binfp) != (size_t) nx)
                error_in_file ("could not read y binary data in file \n%s \n", (filename));
#ifdef XV_MAC
#ifdef MAC_POWERPC
            swap_bytes(ds->xd, nx, sizeof(float));
#endif
#endif
            for (i = 0; i < nx; i++)
                ds->xd[i] = i * dx + abslow ;
            for (i = j = 0; i < nx; i++)
                j = (std::isnan(ds->yd[i]) || std::isnan(ds->xd[i])) ? j + 1 : j;
        }
        else ret = 1;
        ds->nx = nx;
        ds->ny = nx;
        fclose (binfp);
        return (ret) ? -1 : nx;
    }

    int push_bin_float_error_z(one_plot *op, const char *filename, int offset, int nx, int axis)
    {
        char ch;
        int ret = 0;
        size_t len;
        float *array = NULL;
        FILE *binfp;
        data_set *ds = NULL;
        static char previous_file[512];
        static int first = 1;
        static long int cz = 0;

        if (op == NULL)  return 1;
        binfp = fopen (filename, "rb");
        if ( binfp == NULL )
            error_in_file ("binary file not found!...  \n", filename);
        if (first)
        {
            strncpy(previous_file, filename, sizeof(previous_file));
            first = 0;
        }
        len = strlen(filename);
        len = (len > strlen(previous_file)) ? strlen(previous_file) : len;
        if (cz == 0 || strncmp(previous_file, filename, len) != 0 )
        {
            strncpy(previous_file, filename, sizeof(previous_file));
            while (fread (&ch, sizeof (char), 1, binfp) == 1 && ch != CRT_Z);
            cz = ftell(binfp);
            fseek(binfp, offset, SEEK_CUR);
        }
        else fseek(binfp, cz + offset, SEEK_SET);
        if (op->n_dat == 0)   if (init_data_set(op)) return 1;
        ds = op->dat[op->n_dat - 1];

        if (axis == X_AXIS)
        {
            if (ds->xe != NULL) free(ds->xe);
            if ((alloc_data_set_x_error(ds) == NULL) || (ds->xe == NULL))
               error_in_file("I can't create errors !");
            array = ds->xe;
        }
        else if (axis == Y_AXIS)
        {
            if (ds->ye != NULL) free(ds->ye);
            if ((alloc_data_set_y_error(ds) == NULL) || (ds->ye == NULL))
                error_in_file("I can't create errors !");
            array = ds->ye;
        }

        if (array == NULL)
        {
            fclose(binfp);
            error_in_file ("could not create data set error in binary input file \n%s \n", (filename));
        }

        if (fread (array, sizeof(float), nx, binfp) != (size_t) nx)
            error_in_file ("could not read x binary data in file \n%s \n", (filename));
        else ret = 1;
        fclose (binfp);
        return (ret) ? -1 : nx;
    }

    int push_bin_float_data(one_plot *op, const char *filename)
    {
        int i;
        int n_read, ntot = 0;
        float *tmp_y;
        FILE *binfp;

        if (op == NULL)  return 1;
        binfp = fopen (filename, "rb");
        if ( binfp == NULL )
            error_in_file ("%s file not found!...  \n", filename);
        tmp_y = (float *)calloc(GR_SIZE, sizeof(float));
        if (tmp_y == NULL)
        {
            fprintf(stderr, "calloc error \n");
            exit(1);
        }
        do
        {
            n_read = fread ( tmp_y , sizeof (float),  GR_SIZE, binfp);
#ifdef XV_MAC
#ifdef MAC_POWERPC
            swap_bytes(tmp_y, GR_SIZE, sizeof(float));
#endif
#endif
            if ( absf == 0 )
            {
                for ( i = 0; i < n_read ; i++, i++)
                {

                    push_new_data(op, tmp_y[i], tmp_y[i + 1]);
                }
            }
            else if ( absf == 1 || absf == 2 )
            {
                for ( i = 0; i < n_read ; i++)
                {


                    push_new_data(op, counter * dx + abslow, tmp_y[i]);
                    counter++;
                }
            }
            ntot += n_read;
        }
        while (n_read == GR_SIZE);
        if (tmp_y)   free(tmp_y);
        fclose (binfp);
        return ntot;
    }

    int push_bin_int_data(one_plot *op, const char *filename)
    {
        int i;
        int n_read, ntot = 0;
        short int *tmp_y;
        FILE *binfp;

        if (op == NULL)  return 1;
        binfp = fopen (filename, "rb");
        if ( binfp == NULL )
            error_in_file ("%s file not found!...  \n", filename);
        tmp_y = (short int *)calloc(GR_SIZE, sizeof(int));
        if (tmp_y == NULL)
        {
            fprintf(stderr, "calloc error \n");
            exit(1);
        }
        do
        {
            n_read = fread ( tmp_y , sizeof (short int),  GR_SIZE, binfp);
#ifdef XV_MAC
#ifdef MAC_POWERPC
            swap_bytes(tmp_y, GR_SIZE, sizeof(short int));
#endif
#endif
            if ( absf == 0 )
            {
                for ( i = 0; i < n_read ; i++, i++)
                    push_new_data(op, (float)tmp_y[i], (float)tmp_y[i + 1]);
            }
            else if ( absf == 1 || absf == 2 )
            {
                for ( i = 0; i < n_read ; i++)
                {
                    push_new_data(op, counter * dx + abslow, (float)tmp_y[i]);
                    counter++;
                }
            }
            ntot += n_read;
        }
        while (n_read == GR_SIZE);
        if (tmp_y)  free(tmp_y);
        fclose (binfp);
        return ntot;
    }

    int push_plot_label(one_plot *op, float tx, float ty, char *label, int type)
    {
        plot_label *pl;

        if (op == NULL || label == NULL)  return 1;
        pl = (plot_label *)calloc(1, sizeof(struct plot_label));
        if ( pl == NULL )
        {
            fprintf (stderr, "realloc error \n");
            exit(1);
        }
        pl->xla = tx;
        pl->yla = ty;
        pl->text = (char *)strdup(label);
        pl->type = type;
        if (pl->text == NULL)
        {
            fprintf(stderr, "strdup error \n");
            exit(1);
        }
        return    add_one_plot_data (op, IS_PLOT_LABEL, (void *)pl);
    }

    int pltxlimread(one_plot *op, int *argcp, char ***argvp)
    {
        if (op == NULL || argcp == NULL)  return -1;
        if (!gr_numb(&(op->x_lo), argcp, argvp))     return 0;
        if (!gr_numb(&(op->x_hi), argcp, argvp))     return 1;
        op->iopt2 |= X_LIM;
        return 2;
    }
    int pltylimread(one_plot *op, int *argcp, char ***argvp)
    {
        if (op == NULL || argcp == NULL)  return -1;
        if (!gr_numb(&(op->y_lo), argcp, argvp))     return 0;
        if (!gr_numb(&(op->y_hi), argcp, argvp))     return 1;
        op->iopt2 |= Y_LIM;
        return 2;
    }
    int set_plot_opts(one_plot *op, int argc, char **argv, char *line, int check)
    {
        char file_name[66], *cmd, *tmpch;
        float templ, temp1;
        int itemp, decade = 0, type = 0, subtype = 0, offset = 0, n_item = 0;
        unit_set *un;


        file_name[0] = 0;
        while (--argc > 0)
        {
            argv++;
            cmd = argv[0];

            again:
            switch (argv[0][0])
            {
            case '-':       /* option delimeter */
                argv[0]++;
                goto again;
            case 'i':       /* input file */
                if ( argv[0][1] == 'b' && argv[0][2] == 'f' && argv[0][3] == 'z')
                {
                    if (!gr_numbi(&offset, &argc, &argv))   break;
                    if (!gr_numbi(&n_item, &argc, &argv))   break;

                    if (check == 0)
                        push_bin_float_data_z(op, i_f[cur_i_f].filename, offset, n_item);
                }
                else if ( argv[0][1] == 'b' && argv[0][2] == 'f'  )
                {
                    if (argc >= 2)
                    {
                        argc--;
                        argv++;
                        if (plt_data_path[0] != 0)
                            snprintf(file_name, sizeof(file_name), "%s%s", plt_data_path, argv[0]);
                        else snprintf(file_name, sizeof(file_name), "%s", argv[0]);
                        if (check == 0)       push_bin_float_data(op, file_name);
                    }
                }
                else if ( argv[0][1] == 'b' && argv[0][2] == 'i' )
                {
                    if (argc >= 2)
                    {
                        argc--;
                        argv++;
                        if (plt_data_path[0] != 0)
                            snprintf(file_name, sizeof(file_name), "%s%s", plt_data_path, argv[0]);
                        else snprintf(file_name, sizeof(file_name), "%s", argv[0]);
                        if (check == 0)       push_bin_int_data(op, file_name);
                    }
                }
                /* send directly to the output */
                else if ( argv[0][1] == 'd' && argv[0][2] == 'u' )
                {
                    if (argc >= 2)
                    {
                        argc--;
                        argv++;
                        printf("%s\n", argv[0]);
                    }
                }
                else if (argc >= 2)
                {
                    argc--;
                    argv++;
                    cur_i_f++;
                    if (cur_i_f < I_F_SIZE)
                    {
                        if (plt_data_path[0] != 0)
                            snprintf(file_name, sizeof(file_name), "%s%s", plt_data_path, argv[0]);
                        else snprintf(file_name, sizeof(file_name), "%s", argv[0]);
                        i_f[cur_i_f].n_line = 0;
                        i_f[cur_i_f].filename = file_name;
                        i_f[cur_i_f].fpi = fopen(i_f[cur_i_f].filename, "r");
                        if ( i_f[cur_i_f].fpi == NULL)
                            error_in_file("cannot open file\n %s", i_f[cur_i_f].filename);
                    }
                    else
                    {
                        error_in_file("I cannot handle more\nthan %d nested files", I_F_SIZE);
                    }
                }
                break;


            case 'e':       /* input error from file */
                if ( argv[0][1] == 'x' && argv[0][2] == 'b' && argv[0][3] == 'f' && argv[0][4] == 'z')
                {
                    if (!gr_numbi(&offset, &argc, &argv))   break;
                    if (!gr_numbi(&n_item, &argc, &argv))   break;

                    if (check == 0)
                        push_bin_float_error_z(op, i_f[cur_i_f].filename, offset, n_item, X_AXIS);
                }
                if ( argv[0][1] == 'y' && argv[0][2] == 'b' && argv[0][3] == 'f' && argv[0][4] == 'z')
                {
                    if (!gr_numbi(&offset, &argc, &argv))   break;
                    if (!gr_numbi(&n_item, &argc, &argv))   break;

                    if (check == 0)
                        push_bin_float_error_z(op, i_f[cur_i_f].filename, offset, n_item, Y_AXIS);
                }
                else
                {
                    if (argc >= 2)
                    {
                        argc--;
                        argv++;
                        if (check == 0)
                            op->title = Mystrdupre(op->title, argv[0]);
                    }
                }
                break;

            case 'l':       /* label for plot */
                if ( strncmp(argv[0], "lxp", 3) == 0 )
                {
                    if (argc >= 2)
                    {
                        argc--;
                        argv++;
                        if (check == 0)
                            op->x_prime_title = Mystrdupre(op->x_prime_title, argv[0]);
                    }
                }
                else if ( strncmp(argv[0], "lx", 2) == 0 )
                {
                    if (argc >= 2)
                    {
                        argc--;
                        argv++;
                        if (check == 0)
                            op->x_title = Mystrdupre(op->x_title, argv[0]);
                    }
                }
                else if ( strncmp(argv[0], "lyp", 3) == 0 )
                {
                    if (argc >= 2)
                    {
                        argc--;
                        argv++;
                        if (check == 0)
                            op->y_prime_title = Mystrdupre(op->y_prime_title, argv[0]);
                    }
                }
                else if ( strncmp(argv[0], "ly", 2) == 0 )
                {
                    if (argc >= 2)
                    {
                        argc--;
                        argv++;
                        if (check == 0)
                            op->y_title = Mystrdupre(op->y_title, argv[0]);
                    }
                }
                else if ( strncmp(argv[0], "lr", 2) == 0 )
                {
                    if (argc >= 4)
                    {
                        if (!gr_numb(&templ, &argc, &argv))   break;
                        if (!gr_numb(&temp1, &argc, &argv)) break;
                        argc--;
                        argv++;
                        if (check == 0)
                        {
                            if (op->dat[op->n_dat - 1]->nx == 0)
                            {
                                push_plot_label_in_ds(op->dat[op->n_dat - 1], templ, temp1, argv[0], ABS_COORD);
                            }
                            else push_plot_label(op, templ, temp1, argv[0], ABS_COORD);
                        }
                    }
                }
                else if ( strncmp(argv[0], "layr", 4) == 0 )
                {
                    if (argc >= 4)
                    {
                        if (!gr_numb(&templ, &argc, &argv))   break;
                        if (!gr_numb(&temp1, &argc, &argv)) break;
                        argc--;
                        argv++;
                        if (check == 0)
                        {
                            if (op->dat[op->n_dat - 1]->nx == 0)
                            {
                                push_plot_label_in_ds(op->dat[op->n_dat - 1], templ, temp1, argv[0], VERT_LABEL_ABS);
                            }
                            else push_plot_label(op, templ, temp1, argv[0], VERT_LABEL_ABS);
                        }
                    }
                }
                else if ( strncmp(argv[0], "lay", 3) == 0 )
                {
                    if (argc >= 4)
                    {
                        if (!gr_numb(&templ, &argc, &argv))   break;
                        if (!gr_numb(&temp1, &argc, &argv)) break;
                        argc--;
                        argv++;
                        if (check == 0)
                        {
                            if (op->dat[op->n_dat - 1]->nx == 0)
                            {
                                push_plot_label_in_ds(op->dat[op->n_dat - 1], templ, temp1, argv[0], VERT_LABEL_USR);
                            }
                            else push_plot_label(op, templ, temp1, argv[0], VERT_LABEL_USR);
                        }
                    }
                }

                else
                {
                    if (argc >= 2)
                    {
                        argc--;
                        argv++;
                        if (check == 0)
                            op->title = Mystrdupre(op->title, argv[0]);
                    }
                }
                break;
            case 'p':       /* prefix and unit */
                if ( argv[0][1] == 'x' )
                {
                    if (argc >= 3)
                    {
                        argc--;
                        argv++;
                        if ((argv[0][0] != '!' ) && (check == 0))
                            op->x_prefix = Mystrdupre(op->x_prefix, argv[0]);
                        argc--;
                        argv++;
                        if ((argv[0][0] != '!' ) && (check == 0))
                            op->x_unit = Mystrdupre(op->x_unit, argv[0]);
                    }
                    else
                    {
                        error_in_file("-p prefix unit:\nInvalid argument\n"
                                             "%s\nline %s", cmd, line);
                    }
                }
                else if ( argv[0][1] == 'y' )
                {
                    if (argc >= 3)
                    {
                        argc--;
                        argv++;
                        if ((argv[0][0] != '!' ) && (check == 0))
                            op->y_prefix = Mystrdupre(op->y_prefix, argv[0]);
                        argc--;
                        argv++;
                        if ((argv[0][0] != '!' ) && (check == 0))
                            op->y_unit = Mystrdupre(op->y_unit, argv[0]);
                    }
                    else
                    {
                        error_in_file("-p prefix unit:\nInvalid argument\n"
                                             "%s\nline %s", cmd, line);
                    }
                }
                else if ( argv[0][1] == 't' )
                {
                    if (argc >= 3)
                    {
                        argc--;
                        argv++;
                        if ((argv[0][0] != '!' ) && (check == 0))
                            op->t_prefix = Mystrdupre(op->t_prefix, argv[0]);
                        argc--;
                        argv++;
                        if ((argv[0][0] != '!' ) && (check == 0))
                            op->t_unit = Mystrdupre(op->t_unit, argv[0]);
                    }
                    else
                    {

                        error_in_file("-p prefix unit:\nInvalid argument\n"
                                             "%s\nline %s", cmd, line);
                    }
                }
                break;
            case 'd':       /* output device */
                if ( argv[0][1] == 'p' )
                {
                    if (argc >= 2)
                    {
                        argc--;
                        argv++;
                        if ( strncpy(plt_data_path, argv[0], sizeof(plt_data_path)) == NULL)
                            fprintf (stderr, "not valid data path %s   \n", argv[0]);
                    }
                    else
                    {
                        error_in_file("-dp plt_data_path:\nInvalid argument\n"
                                             "%s\nline %s", cmd, line);
                    }
                }
                break;
            case 'm':       /* line mode */
                if ((check == 0) && (op->n_dat != 0))
                {
                    close_data_set(op);
                    init_data_set(op);
                }
                if (!gr_numb(&templ, &argc, &argv))
                    itemp = argv[0][1] - '0';
                else
                    itemp = (int)templ;
                switch (itemp)
                {
                case -'0':  /* null character */
                case 0:
                    if (check == 0) op->dat[op->n_dat - 1]->m = 0;
                    break;
                case 2:
                    if (check == 0) op->dat[op->n_dat - 1]->m = 2;
                    break;
                }
                break;
            case 'a':       /* automatic abscissas */
                if ( strncmp(argv[0], "axp", 3) == 0 )
                {
                    if (!gr_numbi(&itemp, &argc, &argv))    break;
                    if (check == 0) op->c_xu_p = itemp;
                }
                else if ( strncmp(argv[0], "ayp", 3) == 0 )
                {
                    if (!gr_numbi(&itemp, &argc, &argv))    break;
                    if (check == 0) op->c_yu_p = itemp;
                }
                else if ( argv[0][1] == '!')          absf = 0;
                else if ( strncmp(argv[0], "ax", 2) == 0 )
                {
                    if (check == 0) op->dx = 1;
                    if (!gr_numb(&templ, &argc, &argv))  break;
                    if (check == 0) op->dx = templ;
                    if (!gr_numb(&templ, &argc, &argv))  break;
                    if (check == 0) op->ax = templ;
                }
                else if ( strncmp(argv[0], "ay", 2) == 0 )
                {
                    if (check == 0) op->dy = 1;
                    if (!gr_numb(&templ, &argc, &argv))  break;
                    if (check == 0) op->dy = templ;
                    if (!gr_numb(&templ, &argc, &argv))  break;
                    if (check == 0) op->ay = templ;
                }
                else
                {
                    absf = 1;
                    counter = 0;
                    abslow = 0;
                    dx = 1;
                    if (!gr_numb(&dx, &argc, &argv))
                        break;
                    if (gr_numb(&abslow, &argc, &argv))
                        absf = 2;
                }
                break;
            case 'g':       /* grid style */
                if (!gr_numb(&templ, &argc, &argv))
                    itemp = argv[0][1] - '0';
                else
                    itemp = (int)templ;
                switch (itemp)
                {
                case -'0':  /* null character */
                case 0:
                    if (check == 0)   op->iopt |= NOAXES;/*iopt+=NOAXES;*/
                    break;
                case 1:
                    if (check == 0)   op->iopt |= TRIM;/*iopt += TRIM;*/
                    break;
                case 3:
                    if (check == 0)   op->iopt |= AXES_PRIME;
                    break;
                }
                break;
            case 'c':       /* plotting characters */
                if ( strncmp(argv[0], "color", 5) == 0 )
                {
                    if (argc >= 2)
                    {
                        argc--;
                        argv++;
                        if (check == 0)
                        {
                            if (strncmp(argv[0], "black", 5) == 0)
                                op->dat[op->n_dat - 1]->color =  Black;
                            else if (strncmp(argv[0], "blue", 4) == 0)
                                op->dat[op->n_dat - 1]->color =  Blue;
                            else if (strncmp(argv[0], "green", 5) == 0)
                                op->dat[op->n_dat - 1]->color =  Green;
                            else if (strncmp(argv[0], "cyan", 4) == 0)
                                op->dat[op->n_dat - 1]->color =  Cyan;
                            else if (strncmp(argv[0], "red", 3) == 0)
                                op->dat[op->n_dat - 1]->color =  Red;
                            else if (strncmp(argv[0], "magenta", 7) == 0)
                                op->dat[op->n_dat - 1]->color =  Magenta;
                            else if (strncmp(argv[0], "brown", 5) == 0)
                                op->dat[op->n_dat - 1]->color =  Brown;
                            else if (strncmp(argv[0], "lightgray", 9) == 0)
                                op->dat[op->n_dat - 1]->color =  Lightgray;
                            else if (strncmp(argv[0], "darkgray", 8) == 0)
                                op->dat[op->n_dat - 1]->color =  Darkgray;
                            else if (strncmp(argv[0], "lightblue", 9) == 0)
                                op->dat[op->n_dat - 1]->color =  Lightblue;
                            else if (strncmp(argv[0], "lightgreen", 10) == 0)
                                op->dat[op->n_dat - 1]->color =  Lightgreen;
                            else if (strncmp(argv[0], "lightcyan", 9) == 0)
                                op->dat[op->n_dat - 1]->color =  Lightcyan;
                            else if (strncmp(argv[0], "lightred", 8) == 0)
                                op->dat[op->n_dat - 1]->color =  Lightred;
                            else if (strncmp(argv[0], "lightmagenta", 12) == 0)
                                op->dat[op->n_dat - 1]->color =  Lightmagenta;
                            else if (strncmp(argv[0], "yellow", 6) == 0)
                                op->dat[op->n_dat - 1]->color =  Yellow;
                            else if (strncmp(argv[0], "white", 5) == 0)
                                op->dat[op->n_dat - 1]->color =  White;
                        }
                    }
                }
                else
                {
                    if ((check == 0) && (op->n_dat != 0))
                    {
                        close_data_set(op);
                        init_data_set(op);
                    }
                    if (argc >= 2)
                    {
                        if (check == 0)
                            op->dat[op->n_dat - 1]->symb = Mystrdupre(op->dat[op->n_dat - 1]->symb, argv[1]);
                        argv++;
                        argc--;
                    }
                }
                break;
            case 's':
                if ( strncmp(argv[0], "src", 3) == 0 )
                {
                    if (argc >= 2)
                    {
                        argc--;
                        argv++;
                        if (check == 0)
                            op->dat[op->n_dat - 1]->source = Mystrdupre(op->dat[op->n_dat - 1]->source, argv[0]);
                    }
                }
                if ( strncmp(argv[0], "special", 7) == 0 )
                {
                    if (argc >= 2)
                    {
                        argc--;
                        argv++;
                        if (check == 0)
                            add_one_plot_data(op, IS_SPECIAL, (void *)argv[0]);
                    }
                }
                break;

            case 't':       /* transpose x and y */
                if ( strncmp(argv[0], "tus", 3) == 0 )
                {
                    if (argc < 4)
                    {
                        error_in_file("-tus :\nInvalid argument\n"
                                             "%s\nline %s", cmd, line);
                    }
                    itemp = 0;
                    templ = 1;
                    temp1 = 0;
                    if (!gr_numb(&templ, &argc, &argv))      itemp = 1;
                    if (!gr_numb(&temp1, &argc, &argv))     itemp = 1;
                    if (itemp)
                    {
                        error_in_file("-xus :\nInvalid argument\n"
                                             "%s\nline %s", cmd, line);
                    }
                    argc--;
                    argv++;
                    tmpch = strdup(argv[0]);
                    type = 0;
                    decade = 0;
                    subtype = 0;
                    if (argc >= 3)
                    {
                        if (!gr_numbi(&type, &argc, &argv))     itemp = 1;
                        if (!gr_numbi(&decade, &argc, &argv))   itemp = 1;
                        if (!gr_numbi(&subtype, &argc, &argv))  itemp = 2;
                        if (itemp == 1)
                        {
                            error_in_file("-xus :\nInvalid argument\n"
                                                 "%s\nline %s", cmd, line);
                        }
                    }
                    else if (unit_to_type(tmpch, &type, &decade))
                    {
                        error_in_file("-xus :\nInvalid argument\n"
                                             "%s\nline %s", cmd, line);
                    }
                    un = build_unit_set(type, temp1, templ, (char)decade, 0, tmpch);
                    if (tmpch)
                    {
                        free(tmpch);
                        tmpch = NULL;
                    }
                    if (un == NULL)
                    {
                        error_in_file("-tus :\ncan't create\n%s\nline %s"
                                             , cmd, line);
                    }
                    un->sub_type = subtype;
                    if (check == 0)
                        add_one_plot_data (op, IS_T_UNIT_SET, (void *)un);

                }
                else if ( argv[0][1] == 'k' && argv[0][2] == 'x')
                {
                    gr_numb(&templ, &argc, &argv);
                    if (check == 0) op->tick_len_x = templ;
                }
                else if ( argv[0][1] == 'k' && argv[0][2] == 'y')
                {
                    gr_numb(&templ, &argc, &argv);
                    if (check == 0) op->tick_len_y = templ;
                }
                else if ( argv[0][1] == 'k')
                {
                    gr_numb(&templ, &argc, &argv);
                    if (check == 0) op->tick_len = templ;
                }
                else  if ( strncmp(argv[0], "treat", 5) == 0 )
                {
                    if (argc >= 2)
                    {
                        argc--;
                        argv++;
                        if (check == 0)
                            op->dat[op->n_dat - 1]->treatement = Mystrdupre(op->dat[op->n_dat - 1]->treatement, argv[0]);
                    }
                }
                else  if ( strncmp(argv[0], "time", 5) == 0 )
                {
                    if (argc >= 2)
                    {
                        argc--;
                        argv++;
                        if (check == 0)
                        {
                            if (sscanf(argv[0], "%lu", &(op->dat[op->n_dat - 1]->time)) != 1)
                            {
                                error_in_file("Improper time\n\\it %s %s\n%s",
                                                     cmd, argv[0], line);
                            }
                        }
                    }
                }
                else
                {
                    if (check == 0) op->iopt |= CROSS;
                }
                break;
            case 'x':       /* x limits */
                if ( strncmp(argv[0], "xus", 3) == 0 )
                {
                    if (argc < 4)
                    {
                        error_in_file("-xus :\nInvalid argument\n"
                                             "%s\nline %s", cmd, line);
                    }
                    itemp = 0;
                    templ = 1;
                    temp1 = 0;
                    if (!gr_numb(&templ, &argc, &argv))      itemp = 1;
                    if (!gr_numb(&temp1, &argc, &argv))     itemp = 1;
                    if (itemp)
                    {
                        error_in_file("-xus :\nInvalid argument\n"
                                             "%s\nline %s", cmd, line);
                    }
                    argc--;
                    argv++;
                    tmpch = strdup(argv[0]);
                    type = 0;
                    decade = 0;
                    subtype = 0;
                    if (argc >= 3)
                    {
                        if (!gr_numbi(&type, &argc, &argv))     itemp = 1;
                        if (!gr_numbi(&decade, &argc, &argv))   itemp = 1;
                        if (!gr_numbi(&subtype, &argc, &argv))  itemp = 2;
                        if (itemp == 1)
                        {
                            error_in_file("-xus :\nInvalid argument\n"
                                                 "%s\nline %s", cmd, line);
                        }
                    }
                    else if (unit_to_type(tmpch, &type, &decade))
                    {
                        error_in_file("-xus :\nInvalid argument\n"
                                             "%s\nline %s", cmd, line);
                    }
                    un = build_unit_set(type, temp1, templ, (char)decade, 0, tmpch);
                    if (tmpch)
                    {
                        free(tmpch);
                        tmpch = NULL;
                    }
                    if (un == NULL)
                    {
                        error_in_file("-xus :\ncan't create\n%s\nline %s"
                                             , cmd, line);
                    }
                    un->sub_type = subtype;
                    if (check == 0)
                        add_one_plot_data (op, IS_X_UNIT_SET, (void *)un);

                }
                else
                {
                    if (check == 0)
                    {
                        if ( argv[0][1] == 'n') op->iopt2 &= ~X_NUM;
                        else          op->iopt2 |= X_NUM;
                    }
                    if (argc > 1 && argv[1][0] == 'l')
                    {
                        argc--;
                        argv++;
                        if (check == 0) op->iopt |= XLOG;
                    }
                    if (check == 0)       pltxlimread(op, &argc, &argv);
                    else
                    {
                        gr_numb(&templ, &argc, &argv);
                        gr_numb(&templ, &argc, &argv);
                    }
                }
                break;
            case 'y':       /* y limits */
                if ( strncmp(argv[0], "yus", 3) == 0 )
                {
                    if (argc < 4)
                    {
                        error_in_file("-yus :\nInvalid argument\n"
                                             "%s\nline %s", cmd, line);
                    }
                    itemp = 0;
                    templ = 1;
                    temp1 = 0;
                    if (!gr_numb(&templ, &argc, &argv))      itemp = 1;
                    if (!gr_numb(&temp1, &argc, &argv))     itemp = 1;
                    if (itemp)
                    {
                        error_in_file("-yus :\nInvalid argument\n"
                                             "%s\nline %s", cmd, line);
                    }
                    argc--;
                    argv++;
                    tmpch = strdup(argv[0]);
                    type = 0;
                    decade = 0;
                    subtype = 0;
                    if (argc >= 3)
                    {
                        if (!gr_numbi(&type, &argc, &argv))     itemp = 1;
                        if (!gr_numbi(&decade, &argc, &argv))   itemp = 1;
                        if (!gr_numbi(&subtype, &argc, &argv))  itemp = 2;
                        if (itemp == 1)
                        {
                            error_in_file("-yus :\nInvalid argument\n"
                                                 "%s\nline %s", cmd, line);
                        }
                    }
                    else if (unit_to_type(tmpch, &type, &decade))
                    {
                        error_in_file("-yus :\nInvalid argument\n"
                                             "%s\nline %s", cmd, line);
                    }
                    un = build_unit_set(type, temp1, templ, (char)decade, 0, tmpch);
                    if (un == NULL)
                    {
                        error_in_file("-yus :\ncant create\n"
                                             "%s\nline %s", cmd, line);
                    }
                    if (tmpch)
                    {
                        free(tmpch);
                        tmpch = NULL;
                    }
                    un->sub_type = subtype;
                    if (check == 0)
                        add_one_plot_data (op, IS_Y_UNIT_SET, (void *)un);
                }
                else
                {
                    if (check == 0)
                    {
                        if ( argv[0][1] == 'n')       op->iopt2 &= ~Y_NUM;
                        else                      op->iopt2 |= Y_NUM;
                    }
                    if (argc > 1 && argv[1][0] == 'l')
                    {
                        argc--;
                        argv++;
                        if (check == 0) op->iopt |= YLOG;
                    }
                    if (check == 0)   pltylimread(op, &argc, &argv);
                    else
                    {
                        gr_numb(&templ, &argc, &argv);
                        gr_numb(&templ, &argc, &argv);
                    }
                }
                break;
            case 'h':
                if (strncmp(argv[0], "his", 3) == 0)
                {
                    if (argc >= 2)
                    {
                        argc--;
                        argv++;
                        if (check == 0)
                            op->dat[op->n_dat - 1]->history = Mystrdupre(op->dat[op->n_dat - 1]->history, argv[0]);
                    }
                }
                else if (gr_numb(&templ, &argc, &argv))
                {
                    if (check == 0) op->height = templ;
                    sizef++;
                }
                break;
            case 'w':
                if (gr_numb(&templ, &argc, &argv))
                {
                    if (check == 0)   op->width = templ;
                    sizef++;
                }
                break;
            case 'r':
                if (gr_numb(&templ, &argc, &argv))
                {
                    if (check == 0)   op->right = templ;
                    sizef++;
                }
                break;
            case 'u':
                if (gr_numb(&templ, &argc, &argv))
                {
                    if (check == 0)   op->up = templ;
                    sizef++;
                }
                break;
            default:
                if (check == 0)
                {
                    error_in_file("Plot Invalid argument\n"
                                         "%s\nline %s", cmd, line);
                }
                else
                {
                    return ++n_error;
                }
            }
        }
        return 0;
    }

    int init_one_plot(one_plot *op)
    {
        int i;
        unit_set	*un;

        if (op == NULL) return 1;
        op->width = op->height = 1;
        op->right = op->up = 0;
        op->iopt = 0;
        op->iopt2 = X_NUM + Y_NUM;
        op->tick_len = op->tick_len_x = op->tick_len_y = 1;
        op->x_lo = op->x_hi = op->y_lo = op->y_hi = 0;
        op->n_dat = op->cur_dat = op->n_lab = 0;
        op->dx = op->dy = op->dt = 1;
        op->dat = (data_set **)calloc(MAX_DATA,sizeof(data_set*));
        op->lab = (plot_label **)calloc(MAX_DATA,sizeof(plot_label*));
        if (op->dat == NULL || op->lab == NULL) xvin_ptr_error(Out_Of_Memory);
        op->m_lab = op->m_dat = MAX_DATA;
        op->n_xu = op->m_xu = op->c_xu = 0;
        op->n_yu = op->m_yu = op->c_yu = 0;
        op->n_tu = op->m_tu = op->c_tu = 0;
        op->c_xu_p = op->c_yu_p = op->c_tu_p = -1;
        op->filename = NULL;	op->dir = NULL;
        op->title = NULL;	op->x_title = NULL;	op->y_title = NULL;
        op->x_prime_title = op->y_prime_title = NULL;
        op->y_prefix = NULL;	op->x_prefix = NULL;   op->t_prefix = NULL;
        op->x_unit = NULL;	op->y_unit = NULL;     op->t_unit = NULL;
        op->xu = NULL;	op->yu = NULL;  op->tu = NULL;
        un = build_unit_set(IS_RAW_U, 0, 1, 0, 0, NULL);
        if (un == NULL)		xvin_ptr_error(Out_Of_Memory);
        add_one_plot_data (op, IS_X_UNIT_SET, (void *)un);
        un = build_unit_set(IS_RAW_U, 0, 1, 0, 0, NULL);
        if (un == NULL)		xvin_ptr_error(Out_Of_Memory);
        add_one_plot_data (op, IS_Y_UNIT_SET, (void *)un);
        un = build_unit_set(IS_RAW_U, 0, 1, 0, 0, NULL);
        if (un == NULL)		xvin_ptr_error(Out_Of_Memory);
        add_one_plot_data (op, IS_T_UNIT_SET, (void *)un);
        op->need_to_refresh = 1;
            op->data_changing = 0;
            op->transfering_data_to_box = 0;
        op->user_id = 0;
        op->read_only = false;
        for (i = 0; i < 16; i++)
          {
            op->user_ispare[i] = 0;
            op->user_fspare[i] = 0;
          }
        return 0;
    }
    int free_one_plot(one_plot *op)
    {
        int i;

        if (op == NULL) 	xvin_ptr_error(Wrong_Argument);
        for (i=0 ; i< op->n_dat ; i++)	free_data_set(op->dat[i]);
        if (op->dat)  {free(op->dat);  op->dat = NULL;}
        for (i=0 ; i< op->n_lab ; i++)
        {
            if (op->lab[i]->text != NULL) 	free(op->lab[i]->text);
            if (op->lab[i] != NULL) 	free(op->lab[i]);
        }
        if (op->lab)	{free(op->lab);	   op->lab = NULL;}
        if (op->filename != NULL)	free(op->filename);
        if (op->dir != NULL)		free(op->dir);
        if (op->title != NULL)		free(op->title);
        if (op->x_title != NULL)	free(op->x_title);
        if (op->y_title != NULL)	free(op->y_title);
        if (op->x_prime_title != NULL)	free(op->x_prime_title);
        if (op->y_prime_title != NULL)	free(op->y_prime_title);
        if (op->y_prefix != NULL)	free(op->y_prefix);
        if (op->x_prefix != NULL)	free(op->x_prefix);
        if (op->t_prefix != NULL)	free(op->t_prefix);
        if (op->x_unit != NULL)		free(op->x_unit);
        if (op->y_unit != NULL)		free(op->y_unit);
        if (op->t_unit != NULL)		free(op->t_unit);
        if (op->xu != NULL)
        {
            for (i=0 ; i< op->n_xu ; i++)	free_unit_set(op->xu[i]);
            free(op->xu);
        }
        if (op->yu != NULL)
        {
            for (i=0 ; i< op->n_yu ; i++)	free_unit_set(op->yu[i]);
            free(op->yu);
        }
        if (op->tu != NULL)
        {
            for (i=0 ; i< op->n_tu ; i++)	free_unit_set(op->tu[i]);
            free(op->tu);
        }
        free(op);	op = NULL;
        return 0;
    }
    int pltreadfile(one_plot *op, char const  *file_name, int check)
    {
        int i, j, k;
        int load_abort = 0, total_line_read = 0;
        float tmpx, tmpy;
        char *c1, *c2;
        char *line, *line1;
        char **agv, **agvk;
        int agc = 0;

        //setlocale(LC_ALL, "C");

        if (op == NULL)    return MAX_ERROR;
        absf = cur_i_f = n_error =  0;
        counter = 0;
        abslow = 0;
        dx = 1;
        if (aflag)
        {
            absf = 1;
            counter = 0;
            abslow = 0;
            dx = 1;
        }


        i_f[cur_i_f].n_line = 0;
        i_f[cur_i_f].filename = file_name;
        i_f[cur_i_f].fpi = fopen(file_name, "r");
        if ( i_f[cur_i_f].fpi == NULL)
        {
            error_in_file("cannot open file\n");
            return MAX_ERROR;
        }

        line = (char *)calloc(B_LINE, sizeof(char));
        line1 = (char *)calloc(B_LINE, sizeof(char));
        agv = (char **)calloc(OP_SIZE, sizeof(char *));
        agvk = (char **)calloc(OP_SIZE, sizeof(char *));

        if ( line == NULL || line1 == NULL || agv == NULL || agvk == NULL)
        {
            error_in_file("malloc error \n");
            return MAX_ERROR;
        }

        while (load_abort < MAX_ERROR && total_line_read <= check)
        {
            while ((c1 = get_next_line(line)) == NULL && (cur_i_f > 0))
            {
                if (i_f[cur_i_f].fpi != NULL)
                    fclose(i_f[cur_i_f].fpi);
                i_f[cur_i_f].fpi = NULL;
                cur_i_f--;
            }

            if (check)    total_line_read++;
            if ( c1 == NULL)  break;
            line1[0] = 0;
            i = sscanf(line, "%f", &tmpx);
            if (i == 1)   i = sscanf(line, "%f%f", &tmpx, &tmpy);
            if (i == 2)   i = sscanf(line, "%f%f%s", &tmpx, &tmpy, line1);
            if (i == 3) /* may be a label */
            {
                if ( line1[0] == '%') /* start a comment */
                {
                    i = 2;
                    j = 0;
                }
                else if ( line1[0] == '"')/*start as a label*/
                {
                    c1 = strchr(line, '"');
                    c2 = line1;
                    j = get_label(&c1, &c2, line);
                }
                else
                {
                    error_in_file("a label must start and end\nwith a double quote !...\n->%s", line);
                }
                if (j != 0)
                {
                    if (check == 0)
                    {
                        if (op->n_dat > 0 && op->dat[op->n_dat - 1]->nx == 0)
                        {
                            push_plot_label_in_ds(op->dat[op->n_dat - 1], tmpx, tmpy, c2, USR_COORD);
                        }
                        else push_plot_label(op, tmpx, tmpy, c2, USR_COORD);
                    }
                }
                else if ( i == 3 )
                {
                    error_in_file ("empty label !...\n->%s", line);
                }
            }
            if ( i == 2)  /* may be a data point given by x,y */
            {
                if ( absf == 0)
                {
                    if (check == 0) push_new_data(op, tmpx, tmpy);
                }
                else
                {
                    error_in_file ("you can't input an x,y data point\n when you have specified a -a option\n->%s", line);
                }
            }
            if ( i == 1)  /* may be a data point given by y only */
            {
                if ( absf == 1 || absf == 2 )
                {
                    tmpy = counter * dx + abslow;
                    counter++;
                    if (check == 0) push_new_data(op, tmpy, tmpx);
                }
                else
                {
                    error_in_file ("you can't input data point with only y\nwithout specifying the -a option\n->%s", line);
                }
            }
            if ( i == 0 ) /* a command line */
            {
                /* advance to 1st item */
                while (*c1 == ' ' || *c1 == '\t' || *c1 == '#') c1++;
                for (k = 0 ; k < agc ; k++)
                {
                    if (agvk[k] != NULL)      free(agvk[k]);
                    agvk[k] = NULL;
                }
                agc = 1;

                while ( (c1 != NULL) && (*c1 != 0) )
                {
                    if ( *c1 == '%')  *c1 = 0;
                    else if ( *c1 != '"')
                    {
                        if (sscanf(c1, "%s", line1) == 1)
                        {
                            agvk[agc] = agv[agc] = strdup(line1);
                            agc++;
                        }
                        if (agc >= OP_SIZE)
                        {
                            error_in_file ("too many options\nin input line\n->%s", line);
                            load_abort = MAX_ERROR;
                        }
                        if (c1 != NULL && strchr(c1, ' ') != NULL)  c1 = strchr ( c1, ' ');
                        else if (c1 != NULL && strchr(c1, '\t') != NULL) c1 = strchr (c1, '\t');
                        else  *c1 = 0;
                    }
                    else
                    {
                        c2 = line1;
                        c2[0] = 0;
                        if (get_label(&c1, &c2, line))
                        {
                            agvk[agc] = agv[agc] = strdup(c2);
                            agc++;
                        }
                        if (agc >= OP_SIZE)
                        {
                            error_in_file("too many options\nin input line\n->%s", line);
                            load_abort = MAX_ERROR;
                        }
                    }
                    while (*c1 == ' ' || *c1 == '\t' || *c1 == '\n')
                    {
                        c1++;
                    }
                }
                if (agc > 1)
                {
                    if (set_plot_opts(op, agc, agv, line, check) == MAX_ERROR)
                        load_abort = MAX_ERROR;
                }
                for (k = 0 ; k < agc ; k++)
                {
                    if (agvk[k] != NULL)      free(agvk[k]);
                    agvk[k] = NULL;
                }
                agc = 1;
            }
        }
        if (line) free(line);
        if (line1) free(line1);
        if (agv) free(agv);
        if (agvk) free(agvk);
        while ( cur_i_f >= 0 )
        {
            if (i_f[cur_i_f].fpi != NULL)     fclose( i_f[cur_i_f].fpi);
            cur_i_f--;
        }
        if (check == 0)
        {
            for (i = 0, j = 1, op->c_xu = 0; i < op->n_xu && j != 0 ; i++)
            {
                j = 0;
                if (op->ax != op->xu[i]->ax)  j = 1;
                if (op->dx != op->xu[i]->dx)  j = 1;
                if (op->x_unit == NULL || op->xu[i]->name == NULL)    j = 1;
                else if (strncmp(op->xu[i]->name, op->x_unit, strlen(op->x_unit)) != 0) j = 1;
                if (j == 0)   op->c_xu = i;
            }
            for (i = 0, j = 1, op->c_yu = 0; i < op->n_yu && j != 0 ; i++)
            {
                j = 0;
                if (op->ay != op->yu[i]->ax)  j = 1;
                if (op->dy != op->yu[i]->dx)  j = 1;
                if (op->y_unit == NULL || op->yu[i]->name == NULL)    j = 1;
                else if (strncmp(op->yu[i]->name, op->y_unit, strlen(op->y_unit)) != 0) j = 1;
                if (j == 0)   op->c_yu = i;
            }
            for (i = 0, j = 1, op->c_tu = 0; i < op->n_tu && j != 0 ; i++)
            {
                j = 0;
                if (op->at != op->tu[i]->ax)  j = 1;
                if (op->dt != op->tu[i]->dx)  j = 1;
                if (op->t_unit == NULL || op->tu[i]->name == NULL)    j = 1;
                else if (strncmp(op->tu[i]->name, op->t_unit, strlen(op->t_unit)) != 0) j = 1;
                if (j == 0)   op->c_tu = i;
            }
        }
        return n_error;
    }

    data_set* create_and_attach_one_ds(one_plot *op,int nx, int ny, int)
    {
        data_set *ds;
        if ( op == NULL || nx <= 0 || ny <= 0)
            xvin_ptr_error(Out_Of_Memory);
        ds = build_data_set(nx, ny);
        if (ds == NULL)	
            xvin_ptr_error(Out_Of_Memory);
        ds->nx = nx;	ds->ny = ny;
        if (add_one_plot_data(op, IS_DATA_SET, (void*)ds))
            xvin_ptr_error(Out_Of_Memory);
        op->cur_dat = op->n_dat - 1;
        op->need_to_refresh = 1;
        return ds;
    }
}}

namespace legacy
{
    GrData::GrData(std::string fname)
        : _op((one_plot *)calloc(1, sizeof(one_plot)))
    {
        init_one_plot(_op);

        auto ds = create_and_attach_one_ds(_op, GR_SIZE, GR_SIZE, 0);
        ds->nx = ds->ny = 0;
        try { pltreadfile(_op, fname.c_str(), 0); }
        catch(...) 
        {
            free_one_plot(_op);
            _op = nullptr;
            return;
        }
    }

    std::string GrData::title() const
    { return _op == nullptr || _op->title == nullptr ? "" : _op->title; }

    std::string GrData::title(size_t i) const
    { return i >= size() ? "" : _op->dat[i]->source; }

    size_t      GrData::size() const
    { return _op == nullptr ? 0 : _op->n_dat; }

    size_t      GrData::size(bool isx, size_t i) const
    { return i >= size() ? 0 : (isx ? _op->dat[i]->nx : _op->dat[i]->ny); }

    float*      GrData::data(bool isx, size_t i) const
    { return i >= size() ? nullptr : (isx ? _op->dat[i]->xd : _op->dat[i]->yd); }

    GrData::~GrData() { if(_op != nullptr) free_one_plot(_op); }
}

namespace legacy { namespace {
    # define 	IS_ONE_PLOT		1024
    # define 	IS_Z_UNIT_SET		18
    # define    IS_INT_IMAGE        128
    # define    IS_CHAR_IMAGE       256
    # define    IS_FLOAT_IMAGE      512
    # define    IS_COMPLEX_IMAGE    64
    # define    IS_RGB_PICTURE      16384   // 0x4000
    # define    IS_BW_PICTURE       32768  // 0x8000
    # define    IS_UINT_IMAGE       131072  // 0x20000
    # define    IS_LINT_IMAGE       262144  // 0x40000
    # define    IS_RGBA_PICTURE     524288  // 0x80000
    # define    IS_DOUBLE_IMAGE     0x200000
    # define    IS_COMPLEX_DOUBLE_IMAGE 0x400000
    # define    IS_RGB16_PICTURE    0x800000
    # define    IS_RGBA16_PICTURE   0x100000
    
    # define    IS_BITMAP           65636
    
    
    # define    IS_INT          256
    # define    IS_CHAR         128
    # define    IS_FLOAT        512
    
    # define    PLOT_NEED_REFRESH       0x1
    # define    EXTRA_PLOT_NEED_REFRESH         0x2
    # define    PLOTS_NEED_REFRESH      0x3
    # define    BITMAP_NEED_REFRESH     0x4
    # define    INTERNAL_BITMAP_NEED_REFRESH    0x8
    # define    ALL_NEED_REFRESH        0xF
    typedef struct _mcomplex
    {
        float re, im;
    } mcomplex;

    typedef struct _mdcomplex
    {
        double dre, dim;
    } mdcomplex;


    typedef struct _rgb
    {
        unsigned char r, g, b;
    } rgb_t;

    typedef struct _rgba
    {
        unsigned char r, g, b, a;
    } rgba_t;

    typedef struct _rgb16
    {
        short int r, g, b;
    } rgb16_t;

    typedef struct _rgba16
    {
        short int r, g, b, a;
    } rgba16_t;

    union pix                   /* data pointer to pixel */
    {
        unsigned char *ch;
        short int *in;
        unsigned short int *ui;
        int *li;
        float *fl;
        double *db;
        mcomplex *cp;
        mdcomplex *dcp;
        rgb_t *rgb;
        rgba_t *rgba;
        rgb16_t *rgb16;
        rgba16_t *rgba16;
    };

    struct image_data
    {
        int data_type, mode;            /* char, int or float */
        int nx, nxs, nxe;           /* nb of x pixels */
        int ny , nys, nye;          /* nb of y pixels */
        union pix *pixel;           /* the image data */
        union pix **pxl;            /* the array for movie */
        void **mem;                             /* the array containing the starting point of memory of each image */
        int n_f, m_f, c_f;          /* the number of images */
        unsigned char **over;           /* overwrite plane 1 bit */
        time_t time;                    /* date of creation */
        char *source;
        char *history;
        char *treatement;
        char **special;             /* strings for special infos*/
        int n_special, m_special;
        unsigned char win_flag;         /* boundary conditions */
        int movie_on_disk;                      /* specify if in memory or on disk */
        double record_duration;                 /* duration of data acquisition in micro seconds */
        long long record_start;                 /* start of duration of data */
        struct screen_label ** *s_l;             /* an array of screen object with first index
                                                   related to image number in a movie */
        int *n_sl, *m_sl;

        int **user_ispare;                      // integer paramters specific for each image
        float **user_fspare;                      // float paramters specific for each image
        int user_nipar;                         // nb integer paramters specific for each image
        int user_nfpar;                         // nb float paramters specific for each image
        int multi_page;                        // if set memory is cut one chunck per image for movie
        int has_sqaure_pixel;
        float src_parameter[8];        // numerical value of parameter characterizing data (ex. temperature ...)
        char *src_parameter_type[8];   // the description of these parameters
    };

    /* possible mode values */
    # define    LOG_AMP     8
    # define    AMP_2       16
    # define    AMP     32
    # define    RE      64
    # define    IM      128
    # define    KX      256
    # define    KY      512
    # define    PHI     1024
    # define    GREY_LEVEL  0
    # define    R_LEVEL     2048
    # define    RED_ONLY    2049
    # define    G_LEVEL     4096
    # define    GREEN_ONLY  4097
    # define    B_LEVEL     8192
    # define    BLUE_ONLY   8193
    # define    ALPHA_LEVEL 16384
    # define        TRUE_RGB        32768
    
        /* data treatement */
    # define    LOW_PASS    32
    # define    BAND_PASS   64
    # define    HIGH_PASS   128
    # define    BRICK_WALL  8192
    # define    REAL_MODE   512
    # define    COMPLEX_MODE    1024
    
        /* define boundary conditions */
    # define    X_PER       1
    # define    Y_PER       2
    # define    X_NOT_PER   ~X_PER
    # define    Y_NOT_PER   ~Y_PER
    
    # define    DATA_IN_USE 1
    # define    BITMAP_IN_USE   2


}}

namespace legacy {
    typedef struct one_image
    {
        int type;
        char *filename, *dir, *title;   /* The strings defining the titles */
        char *x_title, *y_title, *x_prime_title, *y_prime_title;
        char *x_prefix, *y_prefix, *x_unit, *y_unit;
        char *z_prefix, *t_prefix, *z_unit, *t_unit;
        float width, height, right, up;
        int iopt, iopt2;
        float tick_len;
        float x_lo, x_hi, y_lo, y_hi;
        float z_black, z_white;     /* grey-scale def */
        float z_min, z_max;     /* grey-scale limit */
        float z_Rmin, z_Rmax;     /* Red scale limit */
        float z_Gmin, z_Gmax;     /* Green scale limit */
        float z_Bmin, z_Bmax;     /* Blue scale limit */
        float ax, dx;           /* conversion factor and offset */
        float ay, dy;           /* between pixels and user dim */
        float az, dz;           /* between pixels and user dim */
        float at, dt;           /* between frames and time */
        struct image_data im;
        struct plot_label **lab;    /* labelling in the plot */
        int n_lab, m_lab;
        one_plot **o_p;          /* the series of plot */
        int n_op, m_op;         /* the number of plot */
        int cur_op;         /* the current one */
        unit_set    **xu;           /* x unit set */
        int n_xu, m_xu, c_xu;
        unit_set    **yu;           /* y unit set */
        int n_yu, m_yu, c_yu;
        unit_set    **zu;           /* z unit set */
        int n_zu, m_zu, c_zu;
        unit_set    **tu;           /* t unit set (for movies) */
        int n_tu, m_tu, c_tu;
        int need_to_refresh;
        int buisy_in_thread;
        int data_changing;
        int transfering_data_to_box;
    } O_i;
}

namespace legacy { namespace {
    typedef struct screen_label
    {
        int type;           /* absolute or user defined */
        float xla, yla;     /* the position of label */
        char *text;         /* the text of it */
        float user_val;
    } S_l;



    typedef struct im_max
    {
        int x0, x1, y0, y1, xm, ym, np, inb;            // a rectangle containing the max in pixels
        double xpos, ypos, weight, zmax, dnb, chi2, sigma;      // trap size
    } im_ext;


    typedef struct im_max_array
    {
        struct im_max *ie;
        unsigned int n_ie, m_ie, c_ie;
    } im_ext_ar;

    # define    SET_DATA_IN_USE(oi)         (oi)->buisy_in_thread |= DATA_IN_USE
    # define    SET_BITMAP_IN_USE(oi)           (oi)->buisy_in_thread |= BITMAP_IN_USE
    # define    SET_DATA_NO_MORE_IN_USE(oi) (oi)->buisy_in_thread &= ~DATA_IN_USE
    # define    SET_BITMAP_NO_MORE_IN_USE(oi)   (oi)->buisy_in_thread &= ~BITMAP_IN_USE
    
    # define    IS_DATA_IN_USE(oi)          ((oi)->buisy_in_thread & DATA_IN_USE)
    # define    IS_BITMAP_IN_USE(oi)            ((oi)->buisy_in_thread & BITMAP_IN_USE)
    
    
    
    # define    SET_PLOT_NEED_REFRESH(oi)          (oi)->need_to_refresh |= PLOT_NEED_REFRESH
    # define    SET_EXTRA_PLOT_NEED_REFRESH(oi)        (oi)->need_to_refresh |= EXTRA_PLOT_NEED_REFRESH
    # define    SET_PLOTS_NEED_REFRESH(oi)         (oi)->need_to_refresh |= PLOTS_NEED_REFRESH
    # define    SET_BITMAP_NEED_REFRESH(oi)        (oi)->need_to_refresh |= BITMAP_NEED_REFRESH
    # define    SET_INTERNAL_BITMAP_NEED_REFRESH(oi)   (oi)->need_to_refresh |= INTERNALBITMAP_NEED_REFRESH
    # define    SET_ALL_NEED_REFRESH(oi)           (oi)->need_to_refresh |= ALL_NEED_REFRESH
    
    # define    UNSET_PLOT_NEED_REFRESH(oi)        (oi)->need_to_refresh &= ~PLOT_NEED_REFRESH
    # define    UNSET_EXTRA_PLOT_NEED_REFRESH(oi)      (oi)->need_to_refresh &= ~EXTRA_PLOT_NEED_REFRESH
    # define    UNSET_PLOTS_NEED_REFRESH(oi)           (oi)->need_to_refresh &= ~PLOTS_NEED_REFRESH
    # define    UNSET_BITMAP_NEED_REFRESH(oi)          (oi)->need_to_refresh &= ~BITMAP_NEED_REFRESH
    # define    UNSET_INTERNAL_BITMAP_NEED_REFRESH(oi) (oi)->need_to_refresh &= ~INTERNALBITMAP_NEED_REFRESH
    # define    UNSET_ALL_NEED_REFRESH(oi)         (oi)->need_to_refresh &= ~ALL_NEED_REFRESH
    
    
    
    # define    OI_TYPE_IS_UNSIGNED_CHAR(oi)        (get_oi_type(oi) == \
                                                         IS_CHAR_IMAGE)) ? 1 : 0;
    # define    OI_TYPE_IS_RGB(oi)              (get_oi_type(oi) == \
                                                     IS_RGB_PICTURE)) ? 1 : 0;
    # define    OI_TYPE_IS_RGBA(oi)             (get_oi_type(oi) == \
                                                     IS_RGBA_PICTURE)) ? 1 : 0;
    # define    OI_TYPE_IS_RGB16(oi)                (get_oi_type(oi) == \
                                                         IS_RGB16_PICTURE)) ? 1 : 0;
    # define    OI_TYPE_IS_RGBA16(oi)               (get_oi_type(oi) == \
                                                         IS_RGBA16_PICTURE)) ? 1 : 0;
    # define    OI_TYPE_IS_INT(oi)          (get_oi_type(oi) == \
                                                 IS_INT_IMAGE)) ? 1 : 0;
    # define    OI_TYPE_IS_UNSIGNED_SHORT_INT(oi)   (get_oi_type(oi) == \
                                                         IS_UINT_IMAGE)) ? 1 : 0;
    # define    OI_TYPE_IS_LONG_INT(oi)     (get_oi_type(oi) == \
                                                 IS_LINT_IMAGE)) ? 1 : 0;
    # define    OI_TYPE_IS_FLOAT(oi)            (get_oi_type(oi) == \
                                                     IS_FLOAT_IMAGE)) ? 1 : 0;
    # define    OI_TYPE_IS_DOUBLE(oi)       (get_oi_type(oi) == \
                                                 IS_DOUBLE_IMAGE)) ? 1 : 0;
    # define    OI_TYPE_IS_COMPLEX(oi)      (get_oi_type(oi) == \
                                                 IS_COMPLEX_IMAGE)) ? 1 : 0;
    # define    OI_TYPE_IS_COMPLEX_DOUBLE(oi)   (get_oi_type(oi) == \
                                                     IS_COMPLEX_DOUBLE_IMAGE)) ? 1 : 0;
    
    
    # define    IS_INT_IMAGE        128
    # define    IS_CHAR_IMAGE       256
    # define    IS_FLOAT_IMAGE      512
    # define    IS_COMPLEX_IMAGE    64
    # define    IS_RGB_PICTURE      16384
    # define    IS_BW_PICTURE       32768
    # define    IS_UINT_IMAGE       131072
    # define    IS_LINT_IMAGE       262144
    # define    IS_RGBA_PICTURE     524288
    # define    IS_DOUBLE_IMAGE     0x200000
    # define    IS_COMPLEX_DOUBLE_IMAGE 0x400000
    # define    IS_RGB16_PICTURE    0x800000
    # define    IS_RGBA16_PICTURE   0x100000
    
    # define        UCHAR_LINE_PTR(oi,line)     (oi)->im.pixel[(line)].ch
    # define        SINT_LINE_PTR(oi,line)      (oi)->im.pixel[(line)].in
    # define        UINT_LINE_PTR(oi,line)      (oi)->im.pixel[(line)].ui
    # define        LINT_LINE_PTR(oi,line)      (oi)->im.pixel[(line)].li
    # define        FLT_LINE_PTR(oi,line)       (oi)->im.pixel[(line)].fl
    # define        DBL_LINE_PTR(oi,line)       (oi)->im.pixel[(line)].db
    # define        RGB_LINE_PTR(oi,line)       (oi)->im.pixel[(line)].rgb
    # define        RGBA_LINE_PTR(oi,line)      (oi)->im.pixel[(line)].rgba
    # define        RGB16_LINE_PTR(oi,line)     (oi)->im.pixel[(line)].rgb16
    # define        RGBA16_LINE_PTR(oi,line)    (oi)->im.pixel[(line)].rgba16
    # define        CFLT_LINE_PTR(oi,line)      (oi)->im.pixel[(line)].mcomplex
    # define        CDBL_LINE_PTR(oi,line)      (oi)->im.pixel[(line)].mdcomplex
    
    
    # define        UCHAR_PIXEL(oi,line,col)     (oi)->im.pixel[(line)].ch[(col)]
    # define        SINT_PIXEL(oi,line,col)      (oi)->im.pixel[(line)].in[(col)]
    # define        UINT_PIXEL(oi,line,col)      (oi)->im.pixel[(line)].ui[(col)]
    # define        LINT_PIXEL(oi,line,col)      (oi)->im.pixel[(line)].li[(col)]
    # define        FLT_PIXEL(oi,line,col)       (oi)->im.pixel[(line)].fl[(col)]
    # define        DBL_PIXEL(oi,line,col)       (oi)->im.pixel[(line)].db[(col)]
    # define        RGB_PIXEL(oi,line,col)       (oi)->im.pixel[(line)].rgb[(col)]
    # define        RGBA_PIXEL(oi,line,col)      (oi)->im.pixel[(line)].rgba[(col)]
    # define        RGB16_PIXEL(oi,line,col)     (oi)->im.pixel[(line)].rgb16[(col)]
    # define        RGBA16_PIXEL(oi,line,col)    (oi)->im.pixel[(line)].rgba16[(col)]
    # define        CFLT_PIXEL(oi,line,col)      (oi)->im.pixel[(line)].mcomplex[(col)]
    # define        CDBL_PIXEL(oi,line,col)      (oi)->im.pixel[(line)].mdcomplex[(col)]
    # define    get_oi_horizontal_extend(oi) ((oi) == NULL) ? \
                                                xvin_ptr_error(Wrong_Argument) : (oi)->width
    # define    get_oi_vertical_extend(oi) ((oi) == NULL) ? \
                                              xvin_ptr_error(Wrong_Argument) : (oi)->height

    # define    get_oi_x_user_coordinate(x) (oi)->ax + (oi)->dx * (x)
    # define    get_oi_y_user_coordinate(y) (oi)->ay + (oi)->dy * (y)
    # define    get_oi_z_user_coordinate(z) (oi)->az + (oi)->dz * (z)

    # define    set_oi_grid(oi,on_off)      (oi)->iopt = ((on_off) == ON)\
                                                         ? (oi)->iopt & ~NOAXES :\
                                                                                (oi)->iopt | NOAXES
    # define    get_oi_grid(oi)         (((oi)->opt & NOAXES) \
                                         ? OFF : ON)
    
    
    
    # define    USER        0
    # define    PIXEL       1
    # define    NO_NUMBER   2




    # define    remove_cur_op_from_oi(oi)   remove_from_one_image ((oi),\
                                                                   IS_ONE_PLOT, \
                                                                   (void*)  find_oi_cur_op(oi))
    # define    remove_op_from_oi(oi,op)    remove_from_one_image ((oi),\
                                                                   IS_ONE_PLOT, (void*)(op))
    
    # define    remove_label_from_oi(oi,pl) remove_from_one_image ((oi),\
                                                                   IS_PLOT_LABEL, (void*)(pl))
    # define    remove_x_unit_set_from_oi(oi,un)    \
                                                                                remove_from_one_image ((oi),\
                                                                                                       IS_X_UNIT_SET, (void*)(un))
    # define    remove_y_unit_set_from_oi(oi,un)    \
                                                                                remove_from_one_image ((oi),\
                                                                                                       IS_Y_UNIT_SET, (void*)(un))
    # define    remove_z_unit_set_from_oi(oi,un)    \
                                                                                remove_from_one_image ((oi),\
                                                                                                       IS_Z_UNIT_SET, (void*)(un))
    
    
    # define    get_oi_float_dat(oi, row, line)     (oi)->im.pixel[\
                                                                                (line)].fl[(row)]
    # define    set_oi_float_dat(oi, row, line, val)    (oi)->im.pixel[(line)]\
                                                                                .fl[(row)] = val
    # define    get_oi_int_dat(oi, row, line)       (oi)->im.pixel[(line)]\
                                                                                .in[(row)]
    # define    set_oi_int_dat(oi, row, line, val)  (oi)->im.pixel[(line)]\
                                                                                .in[(row)] = val
    # define    get_oi_char_dat(oi, row, line)      (oi)->im.pixel[(line)]\
                                                                                .ch[(row)]
    # define    set_oi_char_dat(oi, row, line, val)     (oi)->im.pixel[(line)]\
                                                                            .ch[(row)] = val

    # define    inherit_from_oi_to_oi       inherit_from_im_to_im
    # define    inherit_from_oi_to_ds       inherit_from_im_to_ds

    # define PIXEL_0    14
    # define PIXEL_1    28
    # define PIXEL_2    56
    # define Z_MIN      128
    # define Z_MAX      256
    
    
    # define    IM_USR_COOR_LB  0x4000  /* uses im units not pixels(left,bot)*/
    # define    IM_USR_COOR_RT  0x2000  /* uses im units not pixels (rigt,top)*/
    
    # define    IM_SAME_X_AXIS  8
    # define    IM_SAME_Y_AXIS  16
    # define    IM_Z_SAME_AS_X_PLOT_AXIS    32
    # define    IM_Z_SAME_AS_Y_PLOT_AXIS    64
    char data_path[512];
    char f_in[256];
    int add_to_one_image(O_i *oi, int type, void *stuff)
    {
        int i = 0;

        if (stuff == NULL || oi == NULL)  xvin_ptr_error(Wrong_Argument);

        if (type == IS_PLOT_LABEL)
        {
            if (oi->n_lab == oi->m_lab)
            {
                oi->m_lab += MAX_DATA;
                oi->lab = (plot_label **)realloc(oi->lab, oi->m_lab * sizeof(plot_label *));

                if (oi->lab == NULL)  xvin_ptr_error(Out_Of_Memory);
            }

            if (((plot_label *)stuff)->text != NULL)   /* no empty label */
            {
                oi->lab[oi->n_lab] = (plot_label *)stuff;
                oi->n_lab++;
            }

            oi->need_to_refresh |= PLOT_NEED_REFRESH;
        }
        else    if (type == IS_ONE_PLOT)
        {
            if (oi->n_op >=  oi->m_op)
            {
                oi->m_op += MAX_DATA;
                oi->o_p = (one_plot **)realloc(oi->o_p, oi->m_op * sizeof(one_plot *));

                if (oi->o_p == NULL) xvin_ptr_error(Out_Of_Memory);
            }

            oi->o_p[oi->n_op] = (one_plot *)stuff;
            oi->cur_op = oi->n_op;
            oi->n_op++;
            oi->need_to_refresh |= EXTRA_PLOT_NEED_REFRESH | PLOT_NEED_REFRESH;         ;
        }
        else    if (type == IS_SPECIAL)
        {
            if (oi->im.n_special >=  oi->im.m_special)
            {
                oi->im.m_special++;
                oi->im.special = (char **)realloc(oi->im.special, oi->im.m_special * sizeof(char *));

                if (oi->im.special == NULL) xvin_ptr_error(Out_Of_Memory);
            }

            oi->im.special[oi->im.n_special] = Mystrdup((char *)stuff);
            oi->im.n_special++;
            oi->need_to_refresh |= PLOT_NEED_REFRESH;
        }
        else if (type == IS_X_UNIT_SET)
        {
            if (oi->n_xu >= oi->m_xu)
            {
                oi->m_xu += MAX_DATA;
                oi->xu = (unit_set **)realloc(oi->xu, oi->m_xu * sizeof(unit_set *));

                if (oi->xu == NULL) xvin_ptr_error(Out_Of_Memory);
            }

            oi->xu[oi->n_xu] = (unit_set *)stuff;
            ((unit_set *)stuff)->axis = IS_X_UNIT_SET;
            oi->n_xu++;
            oi->need_to_refresh |= PLOT_NEED_REFRESH;
        }
        else if (type == IS_Y_UNIT_SET)
        {
            if (oi->n_yu >= oi->m_yu)
            {
                oi->m_yu += MAX_DATA;
                oi->yu = (unit_set **)realloc(oi->yu, oi->m_yu * sizeof(unit_set *));

                if (oi->yu == NULL) xvin_ptr_error(Out_Of_Memory);
            }

            oi->yu[oi->n_yu] = (unit_set *)stuff;
            ((unit_set *)stuff)->axis = IS_Y_UNIT_SET;
            oi->n_yu++;
            oi->need_to_refresh |= PLOT_NEED_REFRESH;
        }
        else if (type == IS_Z_UNIT_SET)
        {
            if (oi->n_zu >= oi->m_zu)
            {
                oi->m_zu += MAX_DATA;
                oi->zu = (unit_set **)realloc(oi->zu, oi->m_zu * sizeof(unit_set *));

                if (oi->zu == NULL) xvin_ptr_error(Out_Of_Memory);
            }

            oi->zu[oi->n_zu] = (unit_set *)stuff;
            ((unit_set *)stuff)->axis = IS_Z_UNIT_SET;
            oi->n_zu++;
            oi->need_to_refresh |= PLOT_NEED_REFRESH;
        }
        else if (type == IS_T_UNIT_SET)
        {
            if (oi->n_tu >= oi->m_tu)
            {
                oi->m_tu += MAX_DATA;
                oi->tu = (unit_set **) realloc(oi->tu, oi->m_tu * sizeof(unit_set *));

                if (oi->tu == NULL) xvin_ptr_error(Out_Of_Memory);
            }

            oi->tu[oi->n_tu] = (unit_set *)stuff;
            ((unit_set *)stuff)->axis = IS_T_UNIT_SET;
            oi->n_tu++;
            oi->need_to_refresh |= PLOT_NEED_REFRESH;
        }
        else    i = 1;

        return i;
    }

    int add_one_image(O_i *oi, int type, void *stuff)
    {
        if (oi == NULL)  xvin_ptr_error(Wrong_Argument);

        return add_to_one_image(oi, type, stuff);
    }

    int push_image_label(O_i *oi, float tx, float ty, char *label, int type)
    {
        plot_label *pl;

        if (oi == NULL || label == NULL) xvin_ptr_error(Wrong_Argument);

        pl = (plot_label *)calloc(1, sizeof(struct plot_label));

        if (pl == NULL) xvin_ptr_error(Out_Of_Memory);

        pl->xla = tx;
        pl->yla = ty;
        pl->text = strdup(label);
        pl->type = type;

        if (pl->text == NULL) xvin_ptr_error(Out_Of_Memory);

        return  add_one_image(oi, IS_PLOT_LABEL, (void *)pl);
    }


    int imxlimread(O_i *oi, int *argcp, char ***argvp)
    {
      if (oi == NULL || argcp == NULL)      return 1;
        if(!gr_numb(&(oi->x_lo),argcp,argvp))		return 1;
        if(!gr_numb(&(oi->x_hi),argcp,argvp))		return 1;
        oi->iopt2 |= X_LIM;
        return 0;
    }
    int imylimread(O_i *oi, int *argcp, char ***argvp)
    {
      if (oi == NULL || argcp == NULL)      return 1;
        if(!gr_numb(&(oi->y_lo),argcp,argvp))		return 1;
        if(!gr_numb(&(oi->y_hi),argcp,argvp))		return 1;
        oi->iopt2 |= Y_LIM;
        return 0;	
    }
    int imzlimread(O_i *oi, int *argcp, char ***argvp)
    {
      if (oi == NULL || argcp == NULL)      return 1;
        if(!gr_numb(&(oi->z_black),argcp,argvp))	return 1;
        if(!gr_numb(&(oi->z_white),argcp,argvp))	return 1;
        return 0;	
    }

    int find_zmin_zmax(O_i *oi)
    {
        int i, j;
        int mode, *li;
        unsigned char *ch;
        rgba_t *rgba;
        rgb_t *rgb;
        rgba16_t *rgba16;
        rgb16_t *rgb16;
        short int *in;
        unsigned short int *ui;
        float *fl, zmin , zmax, t, zr, zi;
        double *db;

        if (oi == NULL) xvin_ptr_error(Wrong_Argument);

        mode = oi->im.mode;

        if (oi->im.data_type == IS_CHAR_IMAGE)
        {
            zmax = zmin = (float)oi->im.pixel[oi->im.nys].ch[oi->im.nxs];

            for (i = oi->im.nys ; i < oi->im.nye ; i++)
            {
                ch = oi->im.pixel[i].ch;

                for (j = oi->im.nxs ; j < oi->im.nxe ; j++)
                {
                    t = (float)(ch[j]);

                    if (t > zmax)   zmax = t;

                    if (t < zmin)   zmin = t;
                }
            }

            zmax = oi->az + oi->dz * (zmax == zmin) ? zmax + 1 : zmax;
            zmin = oi->az + oi->dz * zmin;
        }
        else    if (oi->im.data_type == IS_RGB_PICTURE)
        {    //YUV conversion
             zmax = zmin = 0.299 * oi->im.pixel[oi->im.nys].rgb[oi->im.nxs].r
                     + 0.587 * oi->im.pixel[oi->im.nys].rgb[oi->im.nxs].g
                     +  0.114 * oi->im.pixel[oi->im.nys].rgb[oi->im.nxs].b;

            for (i = oi->im.nys ; i < oi->im.nye ; i++)
            {
                rgb = oi->im.pixel[i].rgb;

                for (j = oi->im.nxs ; j < oi->im.nxe ; j++)
                {
                    t = 0.299 * rgb[j].r + 0.587 * rgb[j].g +  0.114 *  rgb[j].b;

                    if (t > zmax)   zmax = t;

                    if (t < zmin)   zmin = t;
                }
            }

            zmax = oi->az + oi->dz * (zmax / 3 == zmin / 3) ? (zmax / 3) + 1 : zmax / 3;
            zmin = oi->az + oi->dz * zmin / 3;
        }
        else    if (oi->im.data_type == IS_RGBA_PICTURE)
        {
                zmax = zmin = 0.299 * oi->im.pixel[oi->im.nys].rgba[oi->im.nxs].r
                        + 0.587 * oi->im.pixel[oi->im.nys].rgba[oi->im.nxs].g
                        +  0.114 * oi->im.pixel[oi->im.nys].rgba[oi->im.nxs].b;
            for (i = oi->im.nys ; i < oi->im.nye ; i++)
            {
                rgba = oi->im.pixel[i].rgba;

                for (j = oi->im.nxs ; j < oi->im.nxe ; j++)
                {
                    t = 0.299 * rgba[j].r + 0.587 * rgba[j].g +  0.114 *  rgba[j].b;

                    if (t > zmax)   zmax = t;

                    if (t < zmin)   zmin = t;
                }
            }

            zmax = oi->az + oi->dz * (zmax / 3 == zmin / 3) ? (zmax / 3) + 1 : zmax / 3;
            zmin = oi->az + oi->dz * zmin / 3;
        }
        else    if (oi->im.data_type == IS_RGB16_PICTURE)
        {
             zmax = zmin = 0.299 * oi->im.pixel[oi->im.nys].rgb16[oi->im.nxs].r
                     + 0.587 * oi->im.pixel[oi->im.nys].rgb16[oi->im.nxs].g
                     +  0.114 * oi->im.pixel[oi->im.nys].rgb16[oi->im.nxs].b;

            for (i = oi->im.nys ; i < oi->im.nye ; i++)
            {
                in = oi->im.pixel[i].in;
                rgb16 = oi->im.pixel[i].rgb16;

                for (j = oi->im.nxs ; j < oi->im.nxe ; j++)
                {
                    t = 0.299 * rgb16[j].r + 0.587 * rgb16[j].g +  0.114 *  rgb16[j].b;

                    if (t > zmax)   zmax = t;

                    if (t < zmin)   zmin = t;
                }
            }

            zmax = oi->az + oi->dz * (zmax / 3 == zmin / 3) ? (zmax / 3) + 1 : zmax / 3;
            zmin = oi->az + oi->dz * zmin / 3;
        }
        else    if (oi->im.data_type == IS_RGBA16_PICTURE)
        {
             zmax = zmin = 0.299 * oi->im.pixel[oi->im.nys].rgba16[oi->im.nxs].r
                     + 0.587 * oi->im.pixel[oi->im.nys].rgba16[oi->im.nxs].g
                     +  0.114 * oi->im.pixel[oi->im.nys].rgba16[oi->im.nxs].b;

            for (i = oi->im.nys ; i < oi->im.nye ; i++)
            {
                rgba16 = oi->im.pixel[i].rgba16;

                for (j = oi->im.nxs ; j < oi->im.nxe ; j++)
                {
                     t = 0.299 * rgba16[j].r + 0.587 * rgba16[j].g +  0.114 *  rgba16[j].b;

                    if (t > zmax)   zmax = t;

                    if (t < zmin)   zmin = t;
                }
            }

            zmax = oi->az + oi->dz * (zmax / 3 == zmin / 3) ? (zmax / 3) + 1 : zmax / 3;
            zmin = oi->az + oi->dz * zmin / 3;
        }
        else if (oi->im.data_type == IS_INT_IMAGE)
        {
            zmax = zmin = oi->im.pixel[oi->im.nys].in[oi->im.nxs];

            for (i = oi->im.nys ; i < oi->im.nye ; i++)
            {
                in = oi->im.pixel[i].in;

                for (j = oi->im.nxs ; j < oi->im.nxe ; j++)
                {
                    t = (float)(in[j]);

                    if (t > zmax)   zmax = t;

                    if (t < zmin)   zmin = t;
                }
            }

            zmax = oi->az + oi->dz * (zmax == zmin) ? zmax + 1 : zmax;
            zmin = oi->az + oi->dz * zmin;
        }
        else if (oi->im.data_type == IS_UINT_IMAGE)
        {
            zmax = zmin = oi->im.pixel[oi->im.nys].ui[oi->im.nxs];

            for (i = oi->im.nys ; i < oi->im.nye ; i++)
            {
                ui = oi->im.pixel[i].ui;

                for (j = oi->im.nxs ; j < oi->im.nxe ; j++)
                {
                    t = (float)(ui[j]);

                    if (t > zmax)   zmax = t;

                    if (t < zmin)   zmin = t;
                }
            }

            zmax = oi->az + oi->dz * (zmax == zmin) ? zmax + 1 : zmax;
            zmin = oi->az + oi->dz * zmin;
        }
        else if (oi->im.data_type == IS_LINT_IMAGE)
        {
            zmax = zmin = oi->im.pixel[oi->im.nys].li[oi->im.nxs];

            for (i = oi->im.nys ; i < oi->im.nye ; i++)
            {
                li = oi->im.pixel[i].li;

                for (j = oi->im.nxs ; j < oi->im.nxe ; j++)
                {
                    t = (float)(li[j]);

                    if (t > zmax)   zmax = t;

                    if (t < zmin)   zmin = t;
                }
            }

            zmax = oi->az + oi->dz * (zmax == zmin) ? zmax + 1 : zmax;
            zmin = oi->az + oi->dz * zmin;
        }
        else if (oi->im.data_type == IS_FLOAT_IMAGE)
        {
            zmax = zmin = oi->im.pixel[oi->im.nys].fl[oi->im.nxs];

            for (i = oi->im.nys ; i < oi->im.nye ; i++)
            {
                fl = oi->im.pixel[i].fl;

                for (j = oi->im.nxs ; j < oi->im.nxe ; j++)
                {
                    t = fl[j];

                    if (t > zmax)   zmax = t;

                    if (t < zmin)   zmin = t;
                }
            }
        }
        else if (oi->im.data_type == IS_DOUBLE_IMAGE)
        {
            zmax = zmin = oi->im.pixel[oi->im.nys].db[oi->im.nxs];

            for (i = oi->im.nys ; i < oi->im.nye ; i++)
            {
                db = oi->im.pixel[i].db;

                for (j = oi->im.nxs ; j < oi->im.nxe ; j++)
                {
                    t = db[j];

                    if (t > zmax)   zmax = t;

                    if (t < zmin)   zmin = t;
                }
            }
        }
        else if (oi->im.data_type == IS_COMPLEX_IMAGE)
        {
            zr = oi->im.pixel[oi->im.nys].fl[2 * oi->im.nxs];
            zi = oi->im.pixel[oi->im.nys].fl[2 * oi->im.nxs + 1];

            if (mode == RE)             zmin = zr;
            else if (mode == IM)        zmin = zi;
            else if (mode == AMP)       zmin = sqrt(zr * zr + zi * zi);
            else if (mode == AMP_2)     zmin = zr * zr + zi * zi;
            else if (mode == LOG_AMP)   zmin = (zr * zr + zi * zi > 0) ? log10(zr * zr + zi * zi) : -40.0;
            else return -1;

            zmax = zmin;

            for (i = oi->im.nys ; i < oi->im.nye ; i++)
            {
                fl = oi->im.pixel[i].fl;

                for (j = oi->im.nxs ; j < oi->im.nxe ; j++)
                {
                    zr = fl[2 * j];
                    zi = fl[2 * j + 1];

                    if (mode == RE)     t = zr;
                    else if (mode == IM)    t = zi;
                    else if (mode == AMP)   t = sqrt(zr * zr + zi * zi);
                    else if (mode == AMP_2) t = zr * zr + zi * zi;
                    else if (mode == LOG_AMP)   t = (zr * zr + zi * zi > 0) ? log10(zr * zr + zi * zi) : -40.0;
                    else return 1;

                    if (t > zmax)   zmax = t;

                    if (t < zmin)   zmin = t;
                }
            }
        }
        else if (oi->im.data_type == IS_COMPLEX_DOUBLE_IMAGE)
        {
            zr = oi->im.pixel[oi->im.nys].db[2 * oi->im.nxs];
            zi = oi->im.pixel[oi->im.nys].db[2 * oi->im.nxs + 1];

            if (mode == RE)             zmin = zr;
            else if (mode == IM)        zmin = zi;
            else if (mode == AMP)       zmin = sqrt(zr * zr + zi * zi);
            else if (mode == AMP_2)     zmin = zr * zr + zi * zi;
            else if (mode == LOG_AMP)   zmin = (zr * zr + zi * zi > 0) ? log10(zr * zr + zi * zi) : -40.0;
            else return -1;

            zmax = zmin;

            for (i = oi->im.nys ; i < oi->im.nye ; i++)
            {
                db = oi->im.pixel[i].db;

                for (j = oi->im.nxs ; j < oi->im.nxe ; j++)
                {
                    zr = db[2 * j];
                    zi = db[2 * j + 1];

                    if (mode == RE)     t = zr;
                    else if (mode == IM)    t = zi;
                    else if (mode == AMP)   t = sqrt(zr * zr + zi * zi);
                    else if (mode == AMP_2) t = zr * zr + zi * zi;
                    else if (mode == LOG_AMP)   t = (zr * zr + zi * zi > 0) ? log10(zr * zr + zi * zi) : -40.0;
                    else return 1;

                    if (t > zmax)   zmax = t;

                    if (t < zmin)   zmin = t;
                }
            }
        }
        else return 1;

        oi->z_black = oi->z_min = zmin;
        oi->z_white = oi->z_max = (zmax == zmin) ? zmax + 1 : zmax;
        oi->need_to_refresh |= BITMAP_NEED_REFRESH;
        return 0;
    }

    int alloc_one_image(O_i *oi, int nx, int ny, int type)
    {
        int i = 0, j;
        int data_len = 1, nf = 0;
        char *buf = NULL;


        if (oi == NULL) xvin_ptr_error(Wrong_Argument);

        switch (type)
        {
        case IS_CHAR_IMAGE:
            oi->z_min = 0;
            oi->z_max = 255;
            data_len = 1;
            break;

        case IS_RGB_PICTURE:
            oi->z_min = 0;
            oi->z_max = 255;
            oi->z_Rmin = 0;
            oi->z_Rmax = 255;
            oi->z_Gmin = 0;
            oi->z_Gmax = 255;
            oi->z_Bmin = 0;
            oi->z_Bmax = 255;
            oi->im.mode = TRUE_RGB;
            data_len = 3;
            break;

        case IS_RGBA_PICTURE:
            oi->z_min = 0;
            oi->z_max = 255;
            oi->z_Rmin = 0;
            oi->z_Rmax = 255;
            oi->z_Gmin = 0;
            oi->z_Gmax = 255;
            oi->z_Bmin = 0;
            oi->z_Bmax = 255;
            oi->im.mode = TRUE_RGB;
            data_len = 4;
            break;

        case IS_RGB16_PICTURE:
            oi->z_min = -32768;
            oi->z_max = 32767;
            oi->z_Rmin = -32768;
            oi->z_Rmax = 32767;
            oi->z_Gmin = -32768;
            oi->z_Gmax = 32767;
            oi->z_Bmin = -32768;
            oi->z_Bmax = 32767;
            oi->im.mode = TRUE_RGB;
            data_len = 6;
            break;

        case IS_RGBA16_PICTURE:
            oi->z_min = -32768;
            oi->z_max = 32767;
            oi->z_Rmin = -32768;
            oi->z_Rmax = 32767;
            oi->z_Gmin = -32768;
            oi->z_Gmax = 32767;
            oi->z_Bmin = -32768;
            oi->z_Bmax = 32767;
            oi->im.mode = TRUE_RGB;
            data_len = 8;
            break;

        case IS_INT_IMAGE:
            oi->z_min = -32768;
            oi->z_max = 32767;
            data_len = 2;
            break;

        case IS_UINT_IMAGE:
            oi->z_min = 0;
            oi->z_max = 65536;
            data_len = 2;
            break;

        case IS_LINT_IMAGE:
            oi->z_min = -2e30;
            oi->z_max = 2e30;
            data_len = 4;
            break;

        case IS_FLOAT_IMAGE:
            oi->z_min = -1;
            oi->z_max = 1;
            data_len = 4;
            break;

        case IS_COMPLEX_IMAGE:
            oi->z_min = -1;
            oi->z_max = 1;
            data_len = 8;
            break;

        case IS_DOUBLE_IMAGE:
            oi->z_min = -1;
            oi->z_max = 1;
            data_len = 8;
            break;

        case IS_COMPLEX_DOUBLE_IMAGE:
            oi->z_min = -1;
            oi->z_max = 1;
            data_len = 16;
            break;

        default:
            return 1;
            break;
        };

        if (oi->im.pixel != NULL && oi->im.ny != 0 && oi->im.nx != 0)
            buf = (char *)oi->im.mem[0]; //oi->im.pixel[0].ch;

        if (oi->im.movie_on_disk) nf = 1;
        else nf = (oi->im.n_f > 0) ? oi->im.n_f : 1;

        oi->im.pixel = (union pix *)realloc(oi->im.pixel, ny * nf * sizeof(union pix));

        if (oi->im.pixel == NULL) xvin_ptr_error(Out_Of_Memory);

        if (nf > 1) //oi->im.n_f > 1)
        {
            oi->im.pxl = (union pix **)realloc(oi->im.pxl, nf * sizeof(union pix *));
            oi->im.mem = (void **)realloc(oi->im.mem, nf * sizeof(void *));

            if (oi->im.pxl == NULL  || oi->im.mem == NULL)
                xvin_ptr_error(Out_Of_Memory);
        }
        else
        {
            oi->im.mem = (void **)realloc(oi->im.mem, sizeof(void *));
            oi->im.pxl = (union pix **)realloc(oi->im.pxl, sizeof(union pix *));

            if (oi->im.pxl == NULL  || oi->im.mem == NULL)
                xvin_ptr_error(Out_Of_Memory);
        }

        oi->im.m_f = nf;

        if (oi->im.multi_page == 0)
        {
            buf = (char *) realloc(buf, nf * nx * ny * data_len * sizeof(char));

            if (oi->im.pixel == NULL || buf == NULL)    xvin_ptr_error(Out_Of_Memory);

            oi->im.mem[0] = buf;
        }
        else
        {
            for (i = 0 ; i < nf ; i++)
            {
                buf = (char *) calloc(nx * ny, data_len * sizeof(char));

                if (buf == NULL)    xvin_ptr_error(Out_Of_Memory);

                oi->im.mem[i] = buf;
            }
        }



        for (i = 0 ; i < ny * nf ; i++)
        {
            if (oi->im.multi_page)
                buf = (char *) oi->im.mem[i / ny] + (i % ny) * nx * data_len;

            switch (type)
            {
            case IS_CHAR_IMAGE:
                oi->im.pixel[i].ch = (unsigned char *)buf;

                for (j = 0 ; j < nx ; j++) oi->im.pixel[i].ch[j] = 0;

                break;

            case IS_RGB_PICTURE:
                oi->im.pixel[i].ch = (unsigned char *)buf;

                for (j = 0 ; j < 3 * nx ; j++)   oi->im.pixel[i].ch[j] = 0;

                break;

            case IS_RGBA_PICTURE:
                oi->im.pixel[i].ch = (unsigned char *)buf;

                for (j = 0 ; j < 4 * nx ; j++)   oi->im.pixel[i].ch[j] = 0;

                break;

            case IS_RGB16_PICTURE:
                oi->im.pixel[i].in = (short int *)buf;

                for (j = 0 ; j < 3 * nx ; j++)   oi->im.pixel[i].in[j] = 0;

                break;

            case IS_RGBA16_PICTURE:
                oi->im.pixel[i].in = (short int *)buf;

                for (j = 0 ; j < 4 * nx ; j++)   oi->im.pixel[i].in[j] = 0;

                break;

            case IS_INT_IMAGE:
                oi->im.pixel[i].in = (short int *)buf;

                for (j = 0 ; j < nx ; j++) oi->im.pixel[i].in[j] = 0;

                break;

            case IS_UINT_IMAGE:
                oi->im.pixel[i].ui = (unsigned short int *)buf;

                for (j = 0 ; j < nx ; j++) oi->im.pixel[i].ui[j] = 0;

                break;

            case IS_LINT_IMAGE:
                oi->im.pixel[i].li = (int *)buf;

                for (j = 0 ; j < nx ; j++) oi->im.pixel[i].li[j] = 0;

                break;

            case IS_FLOAT_IMAGE:
                oi->im.pixel[i].fl = (float *)buf;

                for (j = 0 ; j < nx ; j++) oi->im.pixel[i].fl[j] = 0;

                break;

            case IS_COMPLEX_IMAGE:
                oi->im.pixel[i].fl = (float *)buf;

                for (j = 0; j < 2 * nx; j++) oi->im.pixel[i].fl[j] = 0;

                break;

            case IS_DOUBLE_IMAGE:
                oi->im.pixel[i].db = (double *)buf;

                for (j = 0 ; j < nx ; j++) oi->im.pixel[i].db[j] = 0;

                break;

            case IS_COMPLEX_DOUBLE_IMAGE:
                oi->im.pixel[i].db = (double *)buf;

                for (j = 0; j < 2 * nx; j++) oi->im.pixel[i].db[j] = 0;

                break;

            };

            if ((i % ny == 0) && (oi->im.n_f > 0))
            {
                oi->im.pxl[i / ny] = oi->im.pixel + i;

                if (oi->im.multi_page == 0) oi->im.mem[i / ny] = (char *)buf;
            }

            buf += nx * data_len;
        }

        if (oi->im.n_f == 0)        oi->im.pxl[0] = oi->im.pixel;

        oi->im.nxs = oi->im.nys = 0;
        oi->im.nxe = oi->im.nx = nx;
        oi->im.nye = oi->im.ny = ny;
        oi->im.data_type = type;

        if (type == IS_COMPLEX_IMAGE  || type == IS_COMPLEX_DOUBLE_IMAGE)
            oi->im.mode = RE;

        oi->im.s_l = (S_l ** *)calloc(nf, sizeof(S_l **));
        oi->im.m_sl = (int *)calloc(nf, sizeof(int));
        oi->im.n_sl = (int *)calloc(nf, sizeof(int));

        if (oi->im.s_l == NULL || oi->im.n_sl == NULL || oi->im.m_sl == NULL)
            xvin_ptr_error(Out_Of_Memory);

        for (i = 0; i < nf; i++)
        {
            oi->im.s_l[i] = NULL;
            oi->im.n_sl[i] = oi->im.m_sl[i] = 0;
        }

        oi->im.user_ispare = (int **)calloc(nf, sizeof(int *));
        oi->im.user_fspare = (float **)calloc(nf, sizeof(float *));

        if (oi->im.user_ispare == NULL || oi->im.user_fspare == NULL)
            xvin_ptr_error(Out_Of_Memory);

        oi->im.user_nfpar = oi->im.user_nipar = 4;

        for (i = 0; i < nf; i++)
        {
            oi->im.user_ispare[i] = (int *)calloc(oi->im.user_nipar, sizeof(int));
            oi->im.user_fspare[i] = (float *)calloc(oi->im.user_nfpar, sizeof(float));

            if (oi->im.user_ispare[i] == NULL || oi->im.user_fspare[i] == NULL)
                xvin_ptr_error(Out_Of_Memory);
        }

        oi->need_to_refresh |= ALL_NEED_REFRESH;
        return 0;
    }

    int     switch_frame(O_i *oi, int n)
    {
        if (oi == NULL) xvin_ptr_error(Wrong_Argument);

        if (oi->im.movie_on_disk > 0)
            xvin_ptr_error(Wrong_Argument);
        else if (oi->im.n_f <= 1) return -1;
        else
        {
            n = (n >= oi->im.n_f) ? oi->im.n_f - 1 : n;
            n = (n < 0) ? 0 : n;
            oi->im.pixel = oi->im.pxl[n];
        }

        oi->im.c_f = n;
        oi->need_to_refresh |= BITMAP_NEED_REFRESH;
        return n;
    }

    int 	push_image(O_i *oi, char *filename, int type, int mode)
    {
        int i, j;
        char ch;
        int knx, knxs, knxe, kny, knys, knye, nf = 1;
        float kz_black, kz_white;
        FILE *fp;
        union pix *p;	
        
        if (oi == NULL)		return -1;
        if (oi->im.nx <= 0 || oi->im.ny <= 0)	return -1;
        knx = oi->im.nx;
        knxs = oi->im.nxs;
        knxe = oi->im.nxe;
        kny = oi->im.ny;
        knys = oi->im.nys;
        knye = oi->im.nye;	
        nf = (oi->im.n_f > 0) ? oi->im.n_f : 1;
        kz_white = oi->z_white;
        kz_black = oi->z_black;
        fp = fopen (filename, "rb");
        if ( fp == NULL )
        {
            error_in_file("%s\nfile not found!...",filename);
            return -1;
        }
        if (alloc_one_image(oi, oi->im.nx, oi->im.ny, type))
        {
            return -1;
        }
        if (oi->im.movie_on_disk)	
        {
            nf = 1;
        }
        if ( mode == CRT_Z)
        {
            while (fread (&ch, sizeof (char), 1, fp) == 1 && ch != CRT_Z);
            if ( ch != CRT_Z)
            {
                error_in_file("no CRT_Z in %s\nbefore file EOF!...",filename);
                return -1;
            }
        }
        else if ( mode == CMID)
        {
            for (i = 0; i < 4 && (fread (&ch, sizeof (char), 1, fp) == 1); i++); 
        }	

        if (type & IS_CHAR_IMAGE)
        {
            p = oi->im.pixel;
            for (i=0; i< kny * nf ; i++)
            {
                if ( (j = fread ( p[i].ch , sizeof (unsigned char), knx, fp)) != knx)
                    return -1;
            }
        }
        else if (type & IS_RGB_PICTURE)
        {
            p = oi->im.pixel;
            for (i=0; i< kny * nf ; i++)
            {
                if ( (j = fread ( p[i].ch , sizeof (unsigned char), 3*knx, fp)) != 3*knx)
                    return -1;
            }
        }
        else if (type & IS_RGBA_PICTURE)
        {
            p = oi->im.pixel;
            for (i=0 ; i< kny * nf ; i++)
            {
                if ( (j = fread ( p[i].ch , sizeof (unsigned char), 4*knx, fp)) != 4*knx)
                    return -1;
            }
        }
        else if (type & IS_RGB16_PICTURE)
        {
            p = oi->im.pixel;
            for (i=0; i< kny * nf ; i++)
            {
                if ( (j = fread ( p[i].in , sizeof (short int), 3*knx, fp)) != 3*knx)
                    return -1;
            }
        }
        else if (type & IS_RGBA16_PICTURE)
        {
            p = oi->im.pixel;
            for (i=0; i< kny * nf ; i++)
            {
                if ( (j = fread ( p[i].in , sizeof (short int), 4*knx, fp)) != 4*knx)
                    return -1;
            }
        }
        else if (type & IS_FLOAT_IMAGE)
        {
            p = oi->im.pixel;			
            for (i=0; i< kny * nf; i++)
            {
                if ( (j = fread ( p[i].fl , sizeof (float), knx, fp)) != knx)
                    return -1;
            }
        }
        else if (type & IS_DOUBLE_IMAGE)
        {
            p = oi->im.pixel;			
            for (i=0; i< kny * nf; i++)
            {
                if ( (j = fread ( p[i].db , sizeof (double), knx, fp)) != knx)
                    return -1;
            }
        }
        else if (type & IS_COMPLEX_IMAGE)
        {
            p = oi->im.pixel;			
            for (i=0; i< kny * nf ; i++)
            {
                if ( (j = fread ( p[i].fl , sizeof (float), 2*knx, fp)) != 2*knx)
                    return -1;
            }
        }
        else if (type & IS_COMPLEX_DOUBLE_IMAGE)
        {
            p = oi->im.pixel;			
            for (i=0; i< kny * nf ; i++)
            {
                if ( (j = fread ( p[i].db , sizeof (double), 2*knx, fp)) != 2*knx)
                    return -1;
            }
        }
        else if (type & IS_INT_IMAGE)
        {	
            p = oi->im.pixel;			
            for (i=0; i< kny * nf; i++)
            {
                if ( (j = fread ( p[i].in , sizeof (short int), knx, fp)) != knx)
                    return -1;				
            }
        }
        else if (type & IS_UINT_IMAGE)
        {	
            p = oi->im.pixel;			
            for (i=0; i< kny * nf; i++)
            {
                if ( (j = fread ( p[i].ui , sizeof (unsigned short int), knx, fp)) != knx)
                    return -1;				
            }
        }
        else if (type & IS_LINT_IMAGE)
        {	
            p = oi->im.pixel;			
            for (i=0; i< kny * nf; i++)
            {
                if ( (j = fread ( p[i].li , sizeof (int), knx, fp)) != knx)
                    return -1;				
            }
        }
        else
        {
            error_in_file("Unknown type of image !");
            return -1;						
        }
        oi->im.nx = knx;
        oi->im.nxs = (knxs <= 0) ? 0 : knxs;
        oi->im.nxe = (knxe <= 0) ? oi->im.nx : knxe;	
        oi->im.ny = kny;
        oi->im.nys = (knys <= 0) ? 0 : knys;
        oi->im.nye = (knye <= 0) ? oi->im.ny : knye;		
        if (kz_white != 0)	oi->z_white = kz_white;
        if (kz_black != 0)	oi->z_black = kz_black;	
        if (oi->im.n_f > 1)	switch_frame(oi,oi->im.c_f);
        if (kz_white == 0 && kz_black == 0) 
        {
            find_zmin_zmax(oi);
            oi->z_black = oi->z_min;
            oi->z_white = oi->z_max;	
        }
        if (oi->dx != 1 || oi->dy != 1) oi->iopt2 |= IM_USR_COOR_RT;
        if (oi->ax != 0 || oi->ay != 0) oi->iopt2 |= IM_USR_COOR_RT;	
        fclose(fp);
        return 0;
    }

    int set_image_opts(O_i *oi, int argc, char **argv)
    {
        char file_name[512], *cmd, *tmpch;
        float temp, temp1;
        int itemp, decade = 0, type = 0, subtype = 0;
        unit_set *un;
        
        if (oi == NULL) return MAX_ERROR;
        file_name[0] = 0;
        while(--argc > 0)
        {
            argv++;
            cmd = argv[0];
    again:		switch(argv[0][0])
            {
                case '-':		/* option delimeter */
                argv[0]++;
                goto again;	
                case 'i':		/* input file */
                if ( strncmp(argv[0],"imzz",4) == 0 )
                {
                    push_image(oi,f_in,IS_COMPLEX_IMAGE,CRT_Z);
                }		
                if ( strncmp(argv[0],"imzdbz",6) == 0 )
                {
                    push_image(oi,f_in,IS_COMPLEX_DOUBLE_IMAGE,CRT_Z);
                }		
                else if ( strncmp(argv[0],"imzdb",5) == 0 )
                {
                    if (argc >= 2)
                    {
                        argc--;
                        argv++;
                        if (data_path[0] != 0)
                          snprintf(file_name,sizeof(file_name),"%s%s",data_path,argv[0]);
                        else snprintf(file_name,sizeof(file_name),"%s",argv[0]);
                        push_image(oi,file_name,IS_COMPLEX_DOUBLE_IMAGE,0);
                    }
                }
                else if ( strncmp(argv[0],"imz",3) == 0 )
                {
                    if (argc >= 2)
                    {
                        argc--;
                        argv++;
                        if (data_path[0] != 0)
                          snprintf(file_name,sizeof(file_name),"%s%s",data_path,argv[0]);
                        else snprintf(file_name,sizeof(file_name),"%s",argv[0]);
                        push_image(oi,file_name,IS_COMPLEX_IMAGE,0);
                    }
                }
                if ( strncmp(argv[0],"imfz",4) == 0 )
                {
                    push_image(oi,f_in,IS_FLOAT_IMAGE,CRT_Z);
                }		
                else if ( strncmp(argv[0],"imf",3) == 0 )
                {
                    if (argc >= 2)
                    {
                        argc--;
                        argv++;
                        if (data_path[0] != 0)
                          snprintf(file_name,sizeof(file_name),"%s%s",data_path,argv[0]);
                        else snprintf(file_name,sizeof(file_name),"%s",argv[0]);
                        push_image(oi,file_name,IS_FLOAT_IMAGE,0);
                    }
                }
                if ( strncmp(argv[0],"imdbz",5) == 0 )
                {
                    push_image(oi,f_in,IS_DOUBLE_IMAGE,CRT_Z);
                }		
                else if ( strncmp(argv[0],"imdb",4) == 0 )
                {
                    if (argc >= 2)
                    {
                        argc--;
                        argv++;
                        if (data_path[0] != 0)
                          snprintf(file_name,sizeof(file_name),"%s%s",data_path,argv[0]);
                        else snprintf(file_name,sizeof(file_name),"%s",argv[0]);
                        push_image(oi,file_name,IS_DOUBLE_IMAGE,0);
                    }
                }
                else 	if ( strncmp(argv[0],"imiz",4) == 0 )
                {
                    push_image(oi,f_in,IS_INT_IMAGE,CRT_Z);
                }		
                else 	if ( strncmp(argv[0],"imi",3) == 0 )
                {
                    if (argc >= 2)
                    {
                        argc--;
                        argv++;
                        if (data_path[0] != 0)
                          snprintf(file_name,sizeof(file_name),"%s%s",data_path,argv[0]);
                        else snprintf(file_name,sizeof(file_name),"%s",argv[0]);
                        push_image(oi,file_name,IS_INT_IMAGE,0);
                    }
                }			
                else 	if ( strncmp(argv[0],"imuiz",4) == 0 )
                {
                    push_image(oi,f_in,IS_UINT_IMAGE,CRT_Z);
                }		
                else 	if ( strncmp(argv[0],"imui",3) == 0 )
                {
                    if (argc >= 2)
                    {
                        argc--;
                        argv++;
                        if (data_path[0] != 0)
                          snprintf(file_name,sizeof(file_name),"%s%s",data_path,argv[0]);
                        else snprintf(file_name,sizeof(file_name),"%s",argv[0]);
                        push_image(oi,file_name,IS_UINT_IMAGE,0);
                    }
                }			
                else 	if ( strncmp(argv[0],"imliz",4) == 0 )
                {
                    push_image(oi,f_in,IS_LINT_IMAGE,CRT_Z);
                }		
                else 	if ( strncmp(argv[0],"imli",3) == 0 )
                {
                    if (argc >= 2)
                    {
                        argc--;
                        argv++;
                        if (data_path[0] != 0)
                          snprintf(file_name,sizeof(file_name),"%s%s",data_path,argv[0]);
                        else snprintf(file_name,sizeof(file_name),"%s",argv[0]);
                        push_image(oi,file_name,IS_LINT_IMAGE,0);
                    }
                }			
                else 	if ( strncmp(argv[0],"imcz",4) == 0 )
                {
                    push_image(oi,f_in,IS_CHAR_IMAGE,CRT_Z);
                }		
                else 	if ( strncmp(argv[0],"imc",3) == 0 )
                {
                    if (argc >= 2)
                    {
                        argc--;
                        argv++;
                        if (data_path[0] != 0)
                          snprintf(file_name,sizeof(file_name),"%s%s",data_path,argv[0]);
                        else snprintf(file_name,sizeof(file_name),"%s",argv[0]);
                        push_image(oi,file_name,IS_CHAR_IMAGE,0);
                    }
                }			
                else 	if ( strncmp(argv[0],"imrgbz",6) == 0 )
                {
                    push_image(oi,f_in,IS_RGB_PICTURE,CRT_Z);
                }		
                else 	if ( strncmp(argv[0],"imrgb16z",8) == 0 )
                {
                    push_image(oi,f_in,IS_RGB16_PICTURE,CRT_Z);
                }		
                else 	if ( strncmp(argv[0],"imrgbaz",7) == 0 )
                {
                    push_image(oi,f_in,IS_RGBA_PICTURE,CRT_Z);
                }		
                else 	if ( strncmp(argv[0],"imrgba16z",9) == 0 )
                {
                    push_image(oi,f_in,IS_RGBA16_PICTURE,CRT_Z);
                }		
                else 	if ( strncmp(argv[0],"imrgba",6) == 0 )
                {
                    if (argc >= 2)
                    {
                        argc--;
                        argv++;
                        if (data_path[0] != 0)
                          snprintf(file_name,sizeof(file_name),"%s%s",data_path,argv[0]);
                        else snprintf(file_name,sizeof(file_name),"%s",argv[0]);
                        push_image(oi,file_name,IS_RGBA_PICTURE,0);
                    }
                }			
                else 	if ( strncmp(argv[0],"imrgb",5) == 0 )
                {
                    if (argc >= 2)
                    {
                        argc--;
                        argv++;
                        if (data_path[0] != 0)
                          snprintf(file_name,sizeof(file_name),"%s%s",data_path,argv[0]);
                        else snprintf(file_name,sizeof(file_name),"%s",argv[0]);
                        push_image(oi,file_name,IS_RGB_PICTURE,0);
                    }
                }			
                else 	if ( strncmp(argv[0],"imrgba16",8) == 0 )
                {
                    if (argc >= 2)
                    {
                        argc--;
                        argv++;
                        if (data_path[0] != 0)
                          snprintf(file_name,sizeof(file_name),"%s%s",data_path,argv[0]);
                        else snprintf(file_name,sizeof(file_name),"%s",argv[0]);
                        push_image(oi,file_name,IS_RGBA16_PICTURE,0);
                    }
                }			
                else 	if ( strncmp(argv[0],"imrgb16",7) == 0 )
                {
                    if (argc >= 2)
                    {
                        argc--;
                        argv++;
                        if (data_path[0] != 0)
                          snprintf(file_name,sizeof(file_name),"%s%s",data_path,argv[0]);
                        else snprintf(file_name,sizeof(file_name),"%s",argv[0]);
                        push_image(oi,file_name,IS_RGB16_PICTURE,0);
                    }
                }			

                else if (argc >= 2)
                {
                    argc--;
                    argv++;
                    cur_i_f++;
                    if (cur_i_f < I_F_SIZE)
                    {
                        if (data_path[0] != 0)
                          snprintf(file_name,sizeof(file_name),"%s%s",data_path,argv[0]);
                        else snprintf(file_name,sizeof(file_name),"%s",argv[0]);
                        i_f[cur_i_f].n_line = 0;
                        i_f[cur_i_f].filename = file_name;
                        i_f[cur_i_f].fpi = fopen(i_f[cur_i_f].filename,"r");
                        if ( i_f[cur_i_f].fpi == NULL)
                        {
                            error_in_file("cannot open file\n%s",i_f[cur_i_f].filename);
                            return MAX_ERROR;
                        }
                    }
                    else
                    {
                        error_in_file("I cannot handle more\nthan %d nested files",I_F_SIZE);
                        return MAX_ERROR;	
                    }
                }
                break;
                case 'l':		/* label for plot */
                if ( strncmp(argv[0],"lxp",3) == 0 )
                {
                    if (argc >= 2)
                    {
                        argc--;
                        argv++;
                        oi->x_prime_title = Mystrdupre(oi->x_prime_title, argv[0]);
                    }
                }
                else if ( strncmp(argv[0],"lx",2) == 0 )
                {
                    if (argc >= 2)
                    {
                        argc--;
                        argv++;
                        oi->x_title = Mystrdupre(oi->x_title, argv[0]);
                    }
                }
                else if ( strncmp(argv[0],"lyp",3) == 0 )
                {
                    if (argc >= 2)
                    {
                        argc--;
                        argv++;
                        oi->y_prime_title = Mystrdupre(oi->y_prime_title, argv[0]);
                    }
                }
                else if ( strncmp(argv[0],"ly",2) == 0 )
                {
                    if (argc >= 2)
                    {
                        argc--;
                        argv++;
                        oi->y_title = Mystrdupre(oi->y_title, argv[0]);
                    }
                }
                else if ( strncmp(argv[0],"luw",3) == 0 )
                {
                    if (argc >= 4)
                    {
                        if(!gr_numb(&temp,&argc,&argv))	break;
                        if(!gr_numb(&temp1,&argc,&argv)) break;						
                        argc--;
                        argv++;
                        push_image_label(oi,temp,temp1,argv[0],USR_COORD+WHITE_LABEL);			
                    }
                }
                else if ( strncmp(argv[0],"lrw",3) == 0 )
                {
                    if (argc >= 4)
                    {
                        if(!gr_numb(&temp,&argc,&argv))	break;
                        if(!gr_numb(&temp1,&argc,&argv)) break;						
                        argc--;
                        argv++;
                        push_image_label(oi,temp,temp1,argv[0],ABS_COORD+WHITE_LABEL);
                    }
                }	
                else if ( strncmp(argv[0],"lvw",3) == 0 )
                {
                    if (argc >= 4)
                    {
                        if(!gr_numb(&temp,&argc,&argv))	break;
                        if(!gr_numb(&temp1,&argc,&argv)) break;						
                        argc--;
                        argv++;
                        push_image_label(oi,temp,temp1,argv[0],VERT_LABEL_USR+WHITE_LABEL);
                    }
                }		
                else if ( strncmp(argv[0],"lv",2) == 0 )
                {
                    if (argc >= 4)
                    {
                        if(!gr_numb(&temp,&argc,&argv))	break;
                        if(!gr_numb(&temp1,&argc,&argv)) break;						
                        argc--;
                        argv++;
                        push_image_label(oi,temp,temp1,argv[0],VERT_LABEL_USR);
                    }
                }									
                else if ( strncmp(argv[0],"lr",2) == 0 )
                {
                    if (argc >= 4)
                    {
                        if(!gr_numb(&temp,&argc,&argv))	break;
                        if(!gr_numb(&temp1,&argc,&argv)) break;						
                        argc--;
                        argv++;
                        push_image_label(oi,temp,temp1,argv[0],ABS_COORD);
                    }
                }
                else 
                {
                    if (argc >= 2)
                    {
                        argc--;
                        argv++;
                        oi->title = Mystrdupre(oi->title, argv[0]);
                    }
                }
                break;
                case 's':				
                if ( strncmp(argv[0],"src",3) == 0 )
                {
                    if (argc >= 2)
                    {
                        argc--;
                        argv++;
                        oi->im.source = Mystrdupre(oi->im.source, argv[0]);
                    }
                }
                if ( strncmp(argv[0],"special",7) == 0 )
                {
                    if (argc >= 2)
                    {
                        argc--;
                        argv++;
                        add_one_image(oi,IS_SPECIAL,(void*)argv[0]);
                    }
                }
                break;
                case 'n':
                if ( argv[0][1] == 'x')
                {
                    if (!gr_numbi(&(oi->im.nx),&argc,&argv))	break;
                    if (!gr_numbi(&(oi->im.nxs),&argc,&argv))	break;
                    if (!gr_numbi(&(oi->im.nxe),&argc,&argv))	break;
                }
                else if ( argv[0][1] == 'y')
                {
                    if (!gr_numbi(&(oi->im.ny),&argc,&argv))		break;
                    if (!gr_numbi(&(oi->im.nys),&argc,&argv))		break;
                    if (!gr_numbi(&(oi->im.nye),&argc,&argv))		break;
                }
                else if ( argv[0][1] == 'f')
                {
                    if (!gr_numbi(&(oi->im.n_f),&argc,&argv))		break;
                    if (oi->im.movie_on_disk) oi->im.n_f = -abs(oi->im.n_f);
                    if (!gr_numbi(&(oi->im.c_f),&argc,&argv))		break;
                }			
                else
                {
                    error_in_file("%s :Invalid argument\n",cmd);
                }
                break;				
                case 'p':		/* prefix and unit */
                if ( argv[0][1] == 'x' )
                {
                    if (argc >= 3)
                    {
                        argc--;
                        argv++;
                        if (argv[0][0] != '!') 
                            oi->x_prefix = Mystrdupre(oi->x_prefix, argv[0]);
                        argc--;
                        argv++;
                        if (argv[0][0] != '!') 
                            oi->x_unit = Mystrdupre(oi->x_unit, argv[0]);
                    }
                    else
                    {
                        error_in_file("-p prefix unit:\nInvalid argument\n%s",cmd);
                    }
                }	
                else if ( argv[0][1] == 'y' )
                {
                    if (argc >= 3)
                    {
                        argc--;
                        argv++;
                        if ( argv[0][0] != '!' )
                            oi->y_prefix = Mystrdupre(oi->y_prefix, argv[0]);
                        argc--;
                        argv++;
                        if ( argv[0][0] != '!' )
                            oi->y_unit = Mystrdupre(oi->y_unit, argv[0]);
                    }
                    else
                    {
                        error_in_file("-p prefix unit:\nInvalid argument\n%s",cmd);
                    }				
                }
                break;
                case 'd':		/* output device */
                if ( strncmp(argv[0],"duration",8) == 0 )
                {
                    if (argc >= 2)
                    {
                        argc--;
                        argv++;
                        if (sscanf(argv[0],"%lf",&(oi->im.record_duration)) != 1)
                        {
                            error_in_file("Improper duration\n\\it %s %s",cmd,argv[0]);
                        }
                    }
                }

                else if ( argv[0][1] == 'p' )
                {
                    if (argc >= 2)
                    {
                        argc--;
                        argv++;
                        if (strncpy(data_path,argv[0],sizeof(data_path)) == NULL)
                            fprintf(stderr,"not a valid path %s\n",argv[0]);
                    }
                    else
                    {
                        error_in_file("-dp data_path:\nInvalid argument\n%s",cmd);	
                    }
                }	
                break;
                case 'a':		/* automatic abscissas */
                if ( argv[0][1] == 'x')
                {
                    oi->dx = 1;
                    if (!gr_numb(&(oi->dx),&argc,&argv))	break;
                    if (!gr_numb(&(oi->ax),&argc,&argv))	break;
                }
                else if ( argv[0][1] == 'y')
                {
                    oi->dy = 1;
                    if (!gr_numb(&(oi->dy),&argc,&argv))	break;
                    if (!gr_numb(&(oi->ay),&argc,&argv))	break;
                }
                else if ( argv[0][1] == 'z')
                {
                    oi->dz = 1;
                    if (!gr_numb(&(oi->dz),&argc,&argv))	break;
                    if (!gr_numb(&(oi->az),&argc,&argv))	break;
                }
                else 
                {
                    error_in_file("Invalid option\n%s",cmd);
                }
                break;
                case 'g':		/* grid style */
                if (!gr_numb(&temp,&argc,&argv))
                    itemp = argv[0][1]-'0';
                else
                    itemp = temp;
                switch (itemp)
                {
                    case -'0':	/* null character */
                    case 0:
                        oi->iopt |= NOAXES;/*ioit+=NOAXES;*/
                        break;
                    case 1:
                        oi->iopt |= TRIM;/*ioit += TRIM;*/
                        break;
                    case 3:
                        oi->iopt |= AXES_PRIME;
                        break;		
                }
                break;
                case 't':		/* transpose x and y */
                if ( strncmp(argv[0],"tus",3) == 0 )
                {
                    if (argc < 4)
                        error_in_file("-tus :\nInvalid argument\n%s",cmd);
                    itemp = 0; temp = 1; temp1 = 0;
                    if (!gr_numb(&temp,&argc,&argv))		itemp = 1;
                    if (!gr_numb(&temp1,&argc,&argv))		itemp = 1;
                    if(itemp)		
                        error_in_file("-tus :\nInvalid argument\n%s",cmd);
                    argc--;				argv++;
                    tmpch = strdup(argv[0]);
                    type = 0; decade = 0; subtype = 0;
                    if (argc >= 3)
                    {
                        if (!gr_numbi(&type,&argc,&argv))		itemp = 1;
                        if (!gr_numbi(&decade,&argc,&argv))	itemp = 1;
                        if (!gr_numbi(&subtype,&argc,&argv))	itemp = 2;
                        if (itemp == 1)		
                            error_in_file("-tus :\nInvalid argument\n%s",cmd);											
                    }
                    else if (unit_to_type(tmpch,&type,&decade))
                        error_in_file("-tus :\nInvalid argument\n%s",cmd);
                    un = build_unit_set(type, temp1, temp, (char)decade, 0, tmpch);
                    if (tmpch)  {free(tmpch); tmpch = NULL;}
                    if (un == NULL)		error_in_file("-tus :\ncant create\n%s",cmd);
                    un->sub_type = subtype;
                    add_one_image (oi, IS_T_UNIT_SET, (void *)un);
                }

                if ( argv[0][1] == 'k')	
                    gr_numb(&(oi->tick_len),&argc,&argv);
                else	if ( strncmp(argv[0],"treat",5) == 0 )
                {
                    if (argc >= 2)
                    {
                        argc--;
                        argv++;
                        oi->im.treatement = Mystrdupre(oi->im.treatement, argv[0]);
                    }
                }
                else	if ( strncmp(argv[0],"time",5) == 0 )
                {
                    if (argc >= 2)
                    {
                        argc--;
                        argv++;
                        if (sscanf(argv[0],"%lu",&(oi->im.time)) != 1)
                        {
                            error_in_file("Improper time\n\\it %s %s",cmd,argv[0]);
                        }
                    }
                }
                else		oi->iopt |= CROSS;
                break;
                case 'x':		/* x limits */
                if ( strncmp(argv[0],"x-periodic",10) == 0 )
                {	
                    oi->im.win_flag |= X_PER;
                }		
                else if ( strncmp(argv[0],"xus",3) == 0 )
                {
                    if (argc < 4)
                        error_in_file("-xus :\nInvalid argument\n%s",cmd);
                    itemp = 0; temp = 1; temp1 = 0;
                    if (!gr_numb(&temp,&argc,&argv))		itemp = 1;
                    if (!gr_numb(&temp1,&argc,&argv))		itemp = 1;
                    if(itemp)		
                        error_in_file("-xus :\nInvalid argument\n%s",cmd);
                    argc--;				argv++;
                    tmpch = strdup(argv[0]);
                    type = 0; decade = 0; subtype = 0;
                    if (argc >= 3)
                    {
                        if (!gr_numbi(&type,&argc,&argv))		itemp = 1;
                        if (!gr_numbi(&decade,&argc,&argv))	itemp = 1;
                        if (!gr_numbi(&subtype,&argc,&argv))	itemp = 2;
                        if (itemp == 1)		
                            error_in_file("-xus :\nInvalid argument\n%s",cmd);											
                    }
                    else if (unit_to_type(tmpch,&type,&decade))
                        error_in_file("-xus :\nInvalid argument\n%s",cmd);
                    un = build_unit_set(type, temp1, temp, (char)decade, 0, tmpch);
                    if (tmpch) {free(tmpch);  tmpch = NULL;}
                    if (un == NULL)		error_in_file("-xus :\ncant create\n%s",cmd);
                    un->sub_type = subtype;
                    add_one_image (oi, IS_X_UNIT_SET, (void *)un);
                }
                else 
                {
                    if ( argv[0][1] == 'n')	oi->iopt2 &= ~X_NUM;
                    else			oi->iopt2 |= X_NUM;
                    imxlimread(oi,&argc,&argv);
                }
                break;
                case 'y':		/* y limits */
                if ( strncmp(argv[0],"y-periodic",10) == 0 )
                {	
                    oi->im.win_flag |= Y_PER;
                }		
                else if ( strncmp(argv[0],"yus",3) == 0 )
                {
                    if (argc < 4)
                        error_in_file("-yus :\nInvalid argument\n%s",cmd);
                    itemp = 0; temp = 1; temp1 = 0;
                    if (!gr_numb(&temp,&argc,&argv))	itemp = 1;
                    if (!gr_numb(&temp1,&argc,&argv))	itemp = 1;
                    if(itemp)		
                        error_in_file("-yus :\nInvalid argument\n%s",cmd);
                    argc--;				argv++;
                    tmpch = strdup(argv[0]);
                    type = 0; decade = 0; subtype = 0;
                    if (argc >= 3)
                    {
                        if (!gr_numbi(&type,&argc,&argv))		itemp = 1;
                        if (!gr_numbi(&decade,&argc,&argv))	itemp = 1;
                        if (!gr_numbi(&subtype,&argc,&argv))	itemp = 2;
                        if (itemp == 1)		
                            error_in_file("-yus :\nInvalid argument\n%s",cmd);											
                    }
                    else if (unit_to_type(tmpch,&type,&decade))
                        error_in_file("-yus :\nInvalid argument\n%s",cmd);
                    un = build_unit_set(type, temp1, temp, (char)decade, 0, tmpch);
                    if (tmpch) {free(tmpch);  tmpch = NULL;}
                    if (un == NULL)		error_in_file("-yus :\ncant create\n%s",cmd);
                    un->sub_type = subtype;
                    add_one_image (oi, IS_Y_UNIT_SET, (void *)un);
                }
                else 
                {
                    if ( argv[0][1] == 'n')	oi->iopt2 &= ~Y_NUM;
                    else			oi->iopt2 |= Y_NUM;
                    imylimread(oi,&argc,&argv);	
                }
                break;
                case 'z':		/* y limits */
                if ( strncmp(argv[0],"zus",3) == 0 )
                {
                    if (argc < 4)
                        error_in_file("-zus :\nInvalid argument\n%s",cmd);
                    itemp = 0; temp = 1; temp1 = 0;
                    if (!gr_numb(&temp,&argc,&argv))		itemp = 1;
                    if (!gr_numb(&temp1,&argc,&argv))		itemp = 1;
                    if(itemp)		
                        error_in_file("-zus :\nInvalid argument\n%s",cmd);
                    argc--;				argv++;
                    tmpch = strdup(argv[0]);
                    type = 0; decade = 0; subtype = 0;
                    if (argc >= 3)
                    {
                        if (!gr_numbi(&type,&argc,&argv))		itemp = 1;
                        if (!gr_numbi(&decade,&argc,&argv))	itemp = 1;
                        if (!gr_numbi(&subtype,&argc,&argv))	itemp = 2;
                        if (itemp == 1)		
                            error_in_file("-zus :\nInvalid argument\n%s",cmd);											
                    }
                    else if (unit_to_type(tmpch,&type,&decade))
                        error_in_file("-zus :\nInvalid argument\n%s",cmd);
                    un = build_unit_set(type, temp1, temp, (char)decade, 0, tmpch);
                    if (tmpch) {free(tmpch);  tmpch = NULL;}
                    if (un == NULL)		error_in_file("-zus :\ncant create\n%s",cmd);
                    un->sub_type = subtype;
                    add_one_image (oi, IS_Z_UNIT_SET, (void *)un);
                }
                else 		imzlimread(oi,&argc,&argv);
                break;
                case 'h':
                if (strncmp(argv[0],"his",3) == 0)
                {
                    if (argc >= 2)
                    {
                        argc--;
                        argv++;
                        oi->im.history = Mystrdupre(oi->im.history, argv[0]);
                    }
                }
                else gr_numb(&(oi->height),&argc,&argv);
                break;
                case 'w':
                gr_numb(&(oi->width),&argc,&argv);
                break;
                case 'r':
                gr_numb(&(oi->right),&argc,&argv);
                break;
                case 'u':
                gr_numb(&(oi->up),&argc,&argv);
                break;
                default:
                error_in_file("image Invalid argument\n%s",cmd);
            }
        }
        return 0;
    }

    int imreadfile(O_i *oi, char const *file_name)
    {
        int i, j, k;
        int load_abort = 0;
        float tmpx, tmpy;
        char *c1 = NULL;
        char *c2 = NULL;
        char *line = NULL;
        char *line1 = NULL;
        char 	**agv = NULL;
        char **agvk = NULL;
        int 	agc = 0;
        
        //setlocale(LC_ALL, "C");
        if (oi == NULL) return MAX_ERROR;
        cur_i_f = 0;
        n_error = 0;
        oi->z_black = oi->z_white = 0;
        i_f[cur_i_f].n_line = 0;
        i_f[cur_i_f].filename = file_name;
        i_f[cur_i_f].fpi = fopen(i_f[cur_i_f].filename,"r");
        if ( i_f[cur_i_f].fpi == NULL)
        {
            return MAX_ERROR;
        }
        line = (char *)calloc(B_LINE,sizeof(char));
        line1 = (char *)calloc(B_LINE,sizeof(char));	
        agv = (char **)calloc(OP_SIZE,sizeof(char*));		
        agvk = (char **)calloc(OP_SIZE,sizeof(char*));		

        if ( line == NULL || line1 == NULL || agv == NULL || agvk == NULL)
            return MAX_ERROR;

        while ( load_abort < MAX_ERROR) 
        {
            while ((c1 = get_next_line(line)) == NULL && (cur_i_f > 0))
            {
                if (i_f[cur_i_f].fpi != NULL)
                    fclose(i_f[cur_i_f].fpi);
                i_f[cur_i_f].fpi = NULL;
                cur_i_f--;
            }
            if ( c1 == NULL)	break;
            line1[0]=0;
            i = sscanf(line,"%f", &tmpx);
            if (i == 1)	i = sscanf(line,"%f%f", &tmpx, &tmpy);
            if (i == 2)	i = sscanf(line,"%f%f%s",&tmpx,&tmpy,line1);
            if (i == 3) /* may be a label */
            {
                if ( line1[0] == '%') /* start a comment */
                {
                    i = 2;
                    j = 0;
                }
                else if ( line1[0] == '"')/*start as a label*/
                {
                    c1 = strchr(line,'"');
                    c2 = line1;
                    j = get_label(&c1, &c2, line);
                }
                else
                    error_in_file ("a label must start and end\nwith a double quote !...\n->%s",line);
                if ( j ) push_image_label(oi,tmpx,tmpy,c2,USR_COORD);
                else if ( i == 3 )
                    error_in_file("empty label !...\n->%s\n",line);
            }
            if ( i == 2 || i == 1)	/* may be a data point x,y !*/
                error_in_file("you can't input an x,y data point\nfor an image... use a gr region\n->%s",line);
            if ( i == 0 )	/* a command line */
            {
                /* advance to 1st item */
              if (c1 != NULL)
                {
                while (*c1 == ' '||*c1 == '\t'||*c1 == '#') c1++;
                for (k = 0 ; k < agc ; k++)	
                {
                    if (agvk[k] != NULL) 		free(agvk[k]);	
                    agvk[k] = NULL;
                }			
                agc = 1;
                while (  (*c1 != 0) )
                {
                    if ( *c1 == '%')	*c1 = 0;
                    else if ( *c1 != '"')
                    {
                        if (sscanf(c1,"%s",line1) == 1)
                        {
                            agvk[agc] = agv[agc] = strdup(line1);
                            agc++;
                        }
                        if (agc >= OP_SIZE)
                            error_in_file("too many options\nin input line\n->%s",line);
                        if (c1 != NULL && strchr(c1,' ') !=NULL)	c1 = strchr ( c1,' ');
                        else if (c1 != NULL && strchr(c1,'\t') !=NULL) c1 = strchr (c1,'\t');
                        else	*c1 = 0;
                    }
                    else
                    {
                        c2 = line1;
                        c2[0] = 0;
                        if (get_label(&c1,&c2, line))
                        {
                            agvk[agc] = agv[agc] = strdup(c2);
                            agc++;
                        }
                        if (agc >= OP_SIZE)
                            error_in_file("too many options\nin input line\n->%s",line);
                    }
                    if (c1 != NULL)
                      {
                        while ( *c1 == ' ' || *c1 == '\t' || *c1 == '\n' )
                        c1++;
                      }
                }
                }
              if (agc > 1)
                {
                  if (set_image_opts(oi, agc, agv) == MAX_ERROR)
                load_abort = MAX_ERROR;
                }
              for (k = 0 ; k < agc ; k++)	
                {
                  if (agvk[k] != NULL) 		free(agvk[k]);	
                  agvk[k] = NULL;
                }				
              
              /*			for ( ; agc > 0 ; agc--)	free(agvk[agc]);*/
              agc = 1;
            }
        }
        if (line) free(line);
        if (line1) free(line1);	
        if (agv) free(agv);
        if (agvk) free(agvk);	

        while ( cur_i_f >= 0 )
        {
            if (i_f[cur_i_f].fpi != NULL)		fclose(	i_f[cur_i_f].fpi);
            if (i_f[cur_i_f].filename != NULL)	
              {
                i_f[cur_i_f].filename = NULL;
              }
            cur_i_f--;		
        }
        for (i = 0, j = 1, oi->c_xu = 0; i < oi->n_xu && j != 0 ; i++)
        {
            j = 0;
            if (oi->ax != oi->xu[i]->ax) 	j = 1;
            if (oi->dx != oi->xu[i]->dx) 	j = 1;
            if (oi->x_unit == NULL || oi->xu[i]->name == NULL)	j = 1;
            else if (strncmp(oi->xu[i]->name,oi->x_unit,strlen(oi->x_unit)) != 0)	j = 1;
            if (j == 0) 	oi->c_xu = i;
        }
        for (i = 0, j = 1, oi->c_yu = 0; i < oi->n_yu && j != 0 ; i++)
        {
            j = 0;
            if (oi->ay != oi->yu[i]->ax) 	j = 1;
            if (oi->dy != oi->yu[i]->dx) 	j = 1;
            if (oi->y_unit == NULL || oi->yu[i]->name == NULL)	j = 1;
            else if (strncmp(oi->yu[i]->name,oi->y_unit,strlen(oi->y_unit)) != 0)	j = 1;
            if (j == 0) 	oi->c_yu = i;
        }
        for (i = 0, j = 1, oi->c_zu = 0; i < oi->n_zu && j != 0 ; i++)
        {
            j = 0;
            if (oi->az != oi->zu[i]->ax) 	j = 1;
            if (oi->dz != oi->zu[i]->dx) 	j = 1;
            if (oi->z_unit == NULL || oi->zu[i]->name == NULL)	j = 1;
            else if (strncmp(oi->zu[i]->name,oi->z_unit,strlen(oi->z_unit)) != 0)	j = 1;
            if (j == 0) 	oi->c_zu = i;
        }
        for (i = 0, j = 1, oi->c_tu = 0; i < oi->n_tu && j != 0 ; i++)
        {
            j = 0;
            if (oi->at != oi->tu[i]->ax) 	j = 1;
            if (oi->dt != oi->tu[i]->dx) 	j = 1;
            if (oi->t_unit == NULL || oi->tu[i]->name == NULL)	j = 1;
            else if (strncmp(oi->tu[i]->name,oi->t_unit,strlen(oi->t_unit)) != 0)	j = 1;
            if (j == 0) 	oi->c_tu = i;
        }
        return n_error;
    }

    int init_one_image(O_i *oi, int type)
    {
        unit_set    *un;
        int i;

        if (oi == NULL) xvin_ptr_error(Wrong_Argument);

        oi->type = type;
        oi->width = oi->height = 1;
        oi->right = oi->up = 0;
        oi->iopt = 0;
        oi->iopt2 = X_NUM | Y_NUM | IM_USR_COOR_RT;
        oi->tick_len = -1;
        oi->x_lo = oi->x_hi = oi->y_lo = oi->y_hi = 0;
        oi->z_black = oi->z_white = 0;
        oi->dx = oi->dy = oi->dz = oi->dt = 1;
        oi->m_lab = MAX_DATA;
        oi->n_lab = oi->im.nx = oi->im.ny = oi->im.nxs = 0;
        oi->im.nys = oi->im.nxe = oi->im.nye = 0;
        oi->filename = oi->dir = oi->title = NULL;
        oi->x_title = oi->y_title = oi->x_prime_title = oi->y_prime_title = NULL;
        oi->x_prefix = oi->y_prefix = oi->x_unit = oi->y_unit  = NULL;
        oi->z_prefix = oi->t_prefix = oi->z_unit = oi->t_unit  = NULL;

        oi->im.n_special = oi->im.m_special = 0;
        oi->im.special = NULL;
        oi->im.win_flag = X_NOT_PER & Y_NOT_PER;
        oi->im.has_sqaure_pixel = 0;
        oi->lab = (plot_label **)calloc(MAX_DATA, sizeof(plot_label *));

        if (oi->lab == NULL) xvin_ptr_error(Out_Of_Memory);

        oi->n_op = oi->m_op = 0;
        oi->cur_op = -1;
        oi->o_p = NULL;
        oi->im.n_f = oi->im.m_f = oi->im.c_f = 0;
        oi->im.pxl = NULL;
        oi->im.pixel = NULL;
        oi->im.mem = NULL;
        oi->at = oi->ax = oi->ay = oi->az = 0;
        oi->n_xu = oi->m_xu = oi->c_xu = 0;
        oi->n_yu = oi->m_yu = oi->c_yu = 0;
        oi->n_zu = oi->m_zu = oi->c_zu = 0;
        oi->n_tu = oi->m_tu = oi->c_tu = 0;
        oi->xu = NULL;
        oi->yu = NULL;
        oi->zu = NULL;
        oi->tu = NULL;
        un = build_unit_set(IS_RAW_U, 0, 1, 0, 0, NULL);

        if (un == NULL) xvin_ptr_error(Out_Of_Memory);

        add_to_one_image(oi, IS_X_UNIT_SET, (void *)un);
        un = build_unit_set(IS_RAW_U, 0, 1, 0, 0, NULL);

        if (un == NULL) xvin_ptr_error(Out_Of_Memory);

        add_to_one_image(oi, IS_Y_UNIT_SET, (void *)un);
        un = build_unit_set(IS_RAW_U, 0, 1, 0, 0, NULL);

        if (un == NULL) xvin_ptr_error(Out_Of_Memory);

        add_to_one_image(oi, IS_Z_UNIT_SET, (void *)un);
        un = build_unit_set(IS_RAW_U, 0, 1, 0, 0, NULL);

        if (un == NULL) xvin_ptr_error(Out_Of_Memory);

        add_to_one_image(oi, IS_T_UNIT_SET, (void *)un);
        oi->need_to_refresh |= ALL_NEED_REFRESH;
        oi->buisy_in_thread = 0;
        oi->data_changing = 0;
        oi->transfering_data_to_box = 0;
        oi->im.movie_on_disk = 0;
        oi->im.source = NULL;
        oi->im.record_duration = 0;
        oi->im.s_l = NULL;
        oi->im.m_sl = NULL;
        oi->im.n_sl = NULL;
        oi->im.user_ispare = NULL;
        oi->im.user_fspare = NULL;
        oi->im.user_nfpar = oi->im.user_nipar = 0;
        oi->im.multi_page = 0;

        for (i = 0 ; i < 8 ; i++)
        {
            oi->im.src_parameter_type[i] = NULL;
            oi->im.src_parameter[i] = 0;
        }

        return 0;
    }

    int free_one_image(O_i *oi)
    {
        int i, j;
        int data, nf;
        union pix *p;

        if (oi == NULL)     xvin_ptr_error(Wrong_Argument);

        if (oi->im.n_f > 0 && oi->im.pxl != NULL)   p = oi->im.pxl[0];
        else                        p = oi->im.pixel;

        data = oi->im.data_type;

        if (p != NULL)
        {
            if (data == IS_CHAR_IMAGE && p[0].ch != NULL)       free(p[0].ch);
            else if (data == IS_INT_IMAGE && p[0].in != NULL)   free(p[0].in);
            else if (data == IS_RGB_PICTURE && p[0].ch != NULL) free(p[0].ch);
            else if (data == IS_RGB16_PICTURE && p[0].ch != NULL)   free(p[0].ch);
            else if (data == IS_FLOAT_IMAGE && p[0].fl != NULL) free(p[0].fl);
            else if (data == IS_COMPLEX_IMAGE && p[0].fl != NULL)   free(p[0].fl);
            else if (data == IS_UINT_IMAGE && p[0].ui != NULL)  free(p[0].ui);
            else if (data == IS_LINT_IMAGE && p[0].li != NULL)  free(p[0].li);
            else if (data == IS_RGBA_PICTURE && p[0].ch != NULL)    free(p[0].ch);
            else if (data == IS_RGBA16_PICTURE && p[0].ch != NULL)  free(p[0].ch);
            else if (data == IS_DOUBLE_IMAGE && p[0].db != NULL)    free(p[0].db);
            else if (data == IS_COMPLEX_DOUBLE_IMAGE && p[0].db != NULL)    free(p[0].db);
        }

        if (p != NULL)  free(p);

        if (oi->im.pxl != NULL)             free(oi->im.pxl);

        if (oi->im.mem != NULL)             free(oi->im.mem);

        if (oi->im.over != NULL)
        {
            if (oi->im.over[0] != NULL)     free(oi->im.over[0]);

            free(oi->im.over);
        }

        if (oi->im.special != NULL)
        {
            for (i = 0 ; i < oi->im.n_special ; i++)
            {
                if (oi->im.special[i] != NULL)
                    free(oi->im.special[i]);
            }

            if (oi->im.special)  free(oi->im.special);
        }

        if (oi->im.source != NULL)          free(oi->im.source);

        if (oi->im.history != NULL)         free(oi->im.history);

        if (oi->im.treatement != NULL)      free(oi->im.treatement);

        if (oi->filename != NULL)           free(oi->filename);

        if (oi->dir != NULL)                free(oi->dir);

        if (oi->title != NULL)          free(oi->title);

        if (oi->x_title != NULL)            free(oi->x_title);

        if (oi->y_title != NULL)            free(oi->y_title);

        if (oi->x_prime_title != NULL)  free(oi->x_prime_title);

        if (oi->y_prime_title != NULL)  free(oi->y_prime_title);

        if (oi->x_prefix != NULL)       free(oi->x_prefix);

        if (oi->y_prefix != NULL)       free(oi->y_prefix);

        if (oi->x_unit != NULL)         free(oi->x_unit);

        if (oi->y_unit != NULL)         free(oi->y_unit);

        if (oi->z_prefix != NULL)       free(oi->z_prefix);

        if (oi->t_prefix != NULL)       free(oi->t_prefix);

        if (oi->z_unit != NULL)         free(oi->z_unit);

        if (oi->t_unit != NULL)         free(oi->t_unit);

        for (i = 0 ; i < oi->n_lab ; i++)
            if (oi->lab[i]->text != NULL)   free(oi->lab[i]->text);

        free(oi->lab);

        for (i = 0 ; i < oi->n_op ; i++)
            if (oi->o_p[i] != NULL)         free_one_plot(oi->o_p[i]);

        if (oi->o_p != NULL)    free(oi->o_p);

        nf = (oi->im.n_f > 0) ? oi->im.n_f : 1;

        for (i = 0 ; i < nf ; i++)
        {
            if (oi->im.user_ispare != NULL && oi->im.user_ispare[i] != NULL)
            {
                free(oi->im.user_ispare[i]);
                oi->im.user_ispare[i] = NULL;
            }

            if (oi->im.user_fspare != NULL && oi->im.user_fspare[i] != NULL)
            {
                free(oi->im.user_fspare[i]);
                oi->im.user_fspare[i] = NULL;
            }
        }

        if (oi->im.user_ispare != NULL) free(oi->im.user_ispare);

        oi->im.user_ispare = NULL;

        if (oi->im.user_fspare != NULL) free(oi->im.user_fspare);

        oi->im.user_fspare = NULL;




        if (oi->im.s_l != NULL && oi->im.m_sl != NULL && oi->im.n_sl != NULL)
        {
            for (i = 0 ; i < nf ; i++)
            {
                for (j = 0 ; j < oi->im.n_sl[i] ; j++)
                {
                    if (oi->im.s_l[i][j]->text != NULL)  free(oi->im.s_l[i][j]->text);

                    free(oi->im.s_l[i][j]);
                }

                if (oi->im.s_l[i])  free(oi->im.s_l[i]);
            }

            free(oi->im.s_l);
            free(oi->im.m_sl);
            free(oi->im.n_sl);
        }

        if (oi->xu != NULL)
        {
            for (i = 0 ; i < oi->n_xu ; i++)   free_unit_set(oi->xu[i]);

            free(oi->xu);
        }

        if (oi->yu != NULL)
        {
            for (i = 0 ; i < oi->n_yu ; i++)   free_unit_set(oi->yu[i]);

            free(oi->yu);
        }

        if (oi->zu != NULL)
        {
            for (i = 0 ; i < oi->n_zu ; i++)   free_unit_set(oi->zu[i]);

            free(oi->zu);
        }

        for (i = 0 ; i < 8 ; i++)
        {
            if (oi->im.src_parameter_type[i] != NULL)
            {
                free(oi->im.src_parameter_type[i]);
                oi->im.src_parameter_type[i] = NULL;
            }
        }

        free(oi);
        oi = NULL;
        return 0;
    }
}}

namespace legacy
{
    ImData::ImData(std::string fname)
        : _op((one_image *)calloc(1, sizeof(one_image)))
    {
        snprintf(f_in, 256, "%s", fname.c_str());
        init_one_image(_op, 0);
        try { imreadfile(_op, fname.c_str()); }
        catch(...) 
        {
            free_one_image(_op);
            _op = nullptr;
            return;
        }
    }

    std::string ImData::title() const
    { return _op == nullptr || _op->title == nullptr ? "" : _op->title; }

    std::pair<size_t, size_t> ImData::dims() const
    { return {size_t(_op->im.nx), size_t(_op->im.ny)}; }

    bool ImData::isfloat() const { return _op->im.data_type == IS_FLOAT_IMAGE; }
    bool ImData::ischar () const { return _op->im.data_type == IS_CHAR_IMAGE; }
    void ImData::data(void * vout) const
    {
        if (_op->im.data_type == IS_CHAR_IMAGE)
        {
            char * out = (char *) vout;
            for (int i = _op->im.nys ; i < _op->im.nye ; i++)
            {
                auto ch = _op->im.pixel[i].ch;
                for (int j = _op->im.nxs ; j < _op->im.nxe ; j++, ++out)
                    out[0] = ch[j];
            }
        } else if(_op->im.data_type == IS_FLOAT_IMAGE) {
            float * out = (float *) vout;
            for (int i = _op->im.nys ; i < _op->im.nye ; i++)
            {
                float const * ch = _op->im.pixel[i].fl;
                for (int j = _op->im.nxs ; j < _op->im.nxe ; j++, ++out)
                    out[0] = ch[j];
            }
        }
    }

    ImData::~ImData() { if(_op != nullptr) free_one_image(_op); }
}
